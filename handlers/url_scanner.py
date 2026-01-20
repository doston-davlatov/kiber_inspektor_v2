import aiohttp
import asyncio
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple
import ssl
import logging

logger = logging.getLogger(__name__)

class URLScanner:
    def __init__(self):
        self.suspicious_ports = [21, 22, 23, 25, 139, 445, 1433, 3306, 3389, 8080, 8888]
        self.trusted_domains = [
            'google.com', 'youtube.com', 'facebook.com', 'instagram.com',
            'twitter.com', 'github.com', 'microsoft.com', 'apple.com',
            'amazon.com', 'netflix.com', 'telegram.org', 'whatsapp.com'
        ]
        self.free_domains = ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz', '.top', 
                            '.club', '.shop', '.online', '.site', '.web']
    
    async def check_url_multiple_sources(self, url: str) -> List[Dict]:
        """URL ni bir necha manbalar orqali tekshirish"""
        checks = []
        
        # 1. Domain reputatsiyasi
        checks.append(await self.check_domain_reputation(url))
        
        # 2. SSL sertifikati
        checks.append(await self.check_ssl_certificate(url))
        
        # 3. IP reputatsiyasi
        checks.append(await self.check_ip_reputation(url))
        
        # 4. Port skanerlash (parallel)
        port_check = await self.scan_ports_async(url)
        checks.append(port_check)
        
        # 5. URL tuzilishi tekshiruvi
        checks.append(self.check_url_structure(url))
        
        # 6. Qisqartirilgan URL lar
        checks.append(self.check_shortened_url(url))
        
        return checks
    
    async def check_domain_reputation(self, url: str) -> Dict:
        """Domain reputatsiyasini tekshirish"""
        try:
            domain = urlparse(url).netloc
            
            result = {
                "check": "domain_reputation",
                "suspicious": False,
                "details": {}
            }
            
            # Bepul domainlar
            for free_domain in self.free_domains:
                if free_domain in domain:
                    result["suspicious"] = True
                    result["details"]["free_domain"] = True
                    break
            
            # Ishonchli domainlar
            for trusted in self.trusted_domains:
                if domain.endswith(trusted):
                    result["details"]["trusted_domain"] = True
                    break
            
            # Domain uzunligi (phishing uchun)
            if len(domain) > 50:
                result["suspicious"] = True
                result["details"]["long_domain"] = True
            
            # Raqamlar bilan domain
            if sum(c.isdigit() for c in domain) > 5:
                result["suspicious"] = True
                result["details"]["many_digits"] = True
            
            # Subdomain lar soni
            subdomain_count = domain.count('.')
            if subdomain_count > 3:
                result["suspicious"] = True
                result["details"]["many_subdomains"] = subdomain_count
            
            result["details"]["domain"] = domain
            return result
            
        except Exception as e:
            logger.error(f"Domain check error: {e}")
            return {"check": "domain_reputation", "suspicious": False, "error": str(e)}
    
    async def check_ssl_certificate(self, url: str) -> Dict:
        """SSL sertifikatini tekshirish"""
        try:
            domain = urlparse(url).netloc
            
            # HTTPS tekshirish
            if not url.startswith('https://'):
                return {
                    "check": "ssl_certificate",
                    "suspicious": True,
                    "details": {"https": False, "warning": "HTTP protokoli xavfsiz emas"}
                }
            
            # SSL sertifikati tekshirish
            context = ssl.create_default_context()
            
            try:
                with socket.create_connection((domain, 443), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()
                        
                        # Sertifikat muddati
                        import datetime
                        not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        days_left = (not_after - datetime.datetime.now()).days
                        
                        result = {
                            "check": "ssl_certificate",
                            "suspicious": False,
                            "details": {
                                "https": True,
                                "certificate_valid": True,
                                "days_left": days_left,
                                "issuer": dict(x[0] for x in cert['issuer'])
                            }
                        }
                        
                        if days_left < 7:
                            result["suspicious"] = True
                            result["details"]["expiring_soon"] = True
                        
                        return result
                        
            except ssl.SSLError as e:
                return {
                    "check": "ssl_certificate",
                    "suspicious": True,
                    "details": {"ssl_error": str(e), "warning": "SSL sertifikati xatosi"}
                }
                
        except Exception as e:
            logger.error(f"SSL check error: {e}")
            return {
                "check": "ssl_certificate",
                "suspicious": True,
                "details": {"error": str(e), "warning": "SSL tekshiruv xatosi"}
            }
    
    async def check_ip_reputation(self, url: str) -> Dict:
        """IP manzil reputatsiyasini tekshirish"""
        try:
            domain = urlparse(url).netloc
            
            # DNS query
            ip = socket.gethostbyname(domain)
            
            result = {
                "check": "ip_reputation",
                "suspicious": False,
                "details": {"ip": ip}
            }
            
            # Maxsus IP diapazonlari
            ip_obj = ipaddress.ip_address(ip)
            
            # Private IP
            if ip_obj.is_private:
                result["suspicious"] = True
                result["details"]["private_ip"] = True
            
            # Known bad IP ranges
            bad_ranges = [
                ipaddress.ip_network('192.168.0.0/16'),
                ipaddress.ip_network('10.0.0.0/8'),
                ipaddress.ip_network('172.16.0.0/12'),
            ]
            
            for bad_range in bad_ranges:
                if ip_obj in bad_range:
                    result["suspicious"] = True
                    result["details"]["internal_ip"] = True
                    break
            
            # Cloud hosting tekshirish (faqat HTTP so'rov orqali)
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                    async with session.get(f"http://ip-api.com/json/{ip}") as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('hosting') or data.get('proxy'):
                                result["suspicious"] = True
                                result["details"]["hosting_provider"] = True
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"IP check error: {e}")
            return {"check": "ip_reputation", "suspicious": False, "error": str(e)}
    
    async def scan_ports_async(self, url: str) -> Dict:
        """URL ning ochiq portlarini asinxron tekshirish"""
        try:
            domain = urlparse(url).netloc
            ip = socket.gethostbyname(domain)
            
            open_ports = []
            
            # Portlarni parallel tekshirish
            tasks = [self.check_port(ip, port) for port in self.suspicious_ports[:5]]  # Faqat 5 tasi
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for port, is_open in zip(self.suspicious_ports[:5], results):
                if is_open and isinstance(is_open, bool):
                    open_ports.append(port)
            
            result = {
                "check": "port_scan",
                "suspicious": len(open_ports) > 0,
                "details": {"open_ports": open_ports}
            }
            
            if open_ports:
                result["details"]["warning"] = f"{len(open_ports)} ta shubhali port ochiq"
            
            return result
            
        except Exception as e:
            logger.error(f"Port scan error: {e}")
            return {"check": "port_scan", "suspicious": False, "error": str(e)}
    
    async def check_port(self, ip: str, port: int) -> bool:
        """Bitta portni tekshirish"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=1.5
            )
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False
    
    def check_url_structure(self, url: str) -> Dict:
        """URL tuzilishini tekshirish"""
        try:
            parsed = urlparse(url)
            
            result = {
                "check": "url_structure",
                "suspicious": False,
                "details": {}
            }
            
            # URL uzunligi
            if len(url) > 150:
                result["suspicious"] = True
                result["details"]["very_long_url"] = True
            
            # Ko'p parametrlar
            if parsed.query and len(parsed.query) > 100:
                result["suspicious"] = True
                result["details"]["many_parameters"] = True
            
            # Shubhali parametrlar
            suspicious_params = ['password', 'credit', 'card', 'login', 'auth', 'token']
            if any(param in parsed.query.lower() for param in suspicious_params):
                result["suspicious"] = True
                result["details"]["sensitive_parameters"] = True
            
            # URL encoding
            if '%' in url and url.count('%') > 5:
                result["suspicious"] = True
                result["details"]["encoded_url"] = True
            
            # @ belgisi (userinfo)
            if '@' in url:
                result["suspicious"] = True
                result["details"]["userinfo_in_url"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"URL structure check error: {e}")
            return {"check": "url_structure", "suspicious": False, "error": str(e)}
    
    def check_shortened_url(self, url: str) -> Dict:
        """Qisqartirilgan URL larni aniqlash"""
        shortened_domains = [
            'bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 'is.gd',
            'buff.ly', 'adf.ly', 'shorte.st', 'bc.vc', 'po.st',
            'u.to', 'j.mp', 't.co', 'rb.gy', 'cutt.ly'
        ]
        
        domain = urlparse(url).netloc
        
        result = {
            "check": "shortened_url",
            "suspicious": False,
            "details": {}
        }
        
        for short_domain in shortened_domains:
            if domain.endswith(short_domain):
                result["suspicious"] = True
                result["details"]["shortened"] = True
                result["details"]["service"] = short_domain
                break
        
        return result
    
    async def get_url_risk_score(self, url: str) -> Tuple[float, str]:
        """URL risk bahosini hisoblash"""
        checks = await self.check_url_multiple_sources(url)
        
        risk_score = 0
        max_score = 0
        factors = []
        
        for check in checks:
            if check.get("suspicious"):
                risk_score += 20
                max_score += 20
                
                # Qo'shimcha omillar
                details = check.get("details", {})
                if details.get("free_domain"):
                    risk_score += 10
                    factors.append("Bepul domen")
                if details.get("open_ports"):
                    risk_score += len(details["open_ports"]) * 5
                    factors.append(f"{len(details['open_ports'])} ochiq port")
                if details.get("ssl_error"):
                    risk_score += 15
                    factors.append("SSL xatosi")
                if details.get("shortened"):
                    risk_score += 10
                    factors.append("Qisqartirilgan URL")
        
        # Risk darajasi
        risk_percent = min(100, (risk_score / max(max_score, 1)) * 100)
        
        if risk_percent > 70:
            risk_level = "High"
        elif risk_percent > 40:
            risk_level = "Medium"
        elif risk_percent > 20:
            risk_level = "Low"
        else:
            risk_level = "Safe"
        
        return risk_percent, risk_level, factors[:3]

# Global obyekt
url_scanner = URLScanner()
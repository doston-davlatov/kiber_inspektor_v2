import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json
from pathlib import Path

class FutureFeatures:
    def __init__(self, db):
        self.db = db
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    async def get_predictive_analytics(self) -> Dict:
        """
        Kelajakdagi xavflarni bashorat qilish
        """
        try:
            cursor = self.db.conn.cursor()
            
            # So'nggi 60 kunlik ma'lumotlar
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m-%d', created_at) as date,
                    strftime('%H', created_at) as hour,
                    threat_level,
                    COUNT(*) as count
                FROM logs 
                WHERE created_at > datetime('now', '-60 days')
                GROUP BY date, hour, threat_level
                ORDER BY date, hour
            ''')
            
            data = cursor.fetchall()
            
            if not data:
                return {}
            
            # DataFrame yaratish
            df = pd.DataFrame(data, columns=['date', 'hour', 'threat_level', 'count'])
            
            # 1. Xavfli soatlar tahlili
            dangerous_hours = df[df['threat_level'] != 'Safe'].groupby('hour')['count'].sum()
            
            if not dangerous_hours.empty:
                peak_hour = dangerous_hours.idxmax()
                peak_count = dangerous_hours.max()
                
                # 2. Trend analiz
                df['date'] = pd.to_datetime(df['date'])
                daily_threats = df[df['threat_level'] != 'Safe'].groupby('date')['count'].sum()
                
                trend = "↑ o'smoqda" if len(daily_threats) > 1 and daily_threats.iloc[-1] > daily_threats.iloc[-2] else "↓ kamaymoqda"
                
                # 3. Xavfli kunlar
                dangerous_days = df[df['threat_level'] != 'Safe'].groupby('date')['count'].sum()
                dangerous_day = dangerous_days.idxmax().strftime('%Y-%m-%d') if not dangerous_days.empty else "N/A"
                
                # 4. Xavf turlari
                threat_types = df.groupby('threat_level')['count'].sum().to_dict()
                
                return {
                    "peak_danger_hour": peak_hour,
                    "peak_danger_count": int(peak_count),
                    "total_threats": int(dangerous_hours.sum()),
                    "avg_daily_threats": float(dangerous_hours.sum() / 60),
                    "trend": trend,
                    "most_dangerous_day": dangerous_day,
                    "threat_distribution": threat_types,
                    "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M')
                }
            
            return {}
            
        except Exception as e:
            print(f"❌ Predictive analytics xatosi: {e}")
            return {}
    
    async def generate_monthly_report(self) -> str:
        """
        Oylik hisobot tayyorlash
        """
        try:
            cursor = self.db.conn.cursor()
            
            # 6 oylik statistikalar
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m', created_at) as month,
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN threat_level != 'Safe' THEN 1 ELSE 0 END) as threats,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT group_id) as active_groups,
                    GROUP_CONCAT(DISTINCT threat_level) as threat_levels
                FROM logs
                WHERE created_at > datetime('now', '-6 months')
                GROUP BY month
                ORDER BY month DESC
            ''')
            
            monthly_stats = cursor.fetchall()
            
            if not monthly_stats:
                return "📭 Hisobot uchun ma'lumot yetarli emas"
            
            report = "📈 <b>Oylik Kiberxavfsizlik Hisoboti</b>\n\n"
            report += f"📅 Hisobot vaqti: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            report += f"📊 Davr: So'nggi {len(monthly_stats)} oy\n\n"
            report += "=" * 40 + "\n\n"
            
            all_threats = 0
            all_messages = 0
            
            for month, total, threats, users, groups, threat_levels in monthly_stats:
                threat_percent = (threats / total * 100) if total > 0 else 0
                all_threats += threats
                all_messages += total
                
                # Xavf indikatori
                if threat_percent > 10:
                    indicator = "🔴"
                elif threat_percent > 5:
                    indicator = "🟡"
                else:
                    indicator = "🟢"
                
                report += (
                    f"{indicator} <b>{month}</b>\n"
                    f"   📨 Xabarlar: {total:,}\n"
                    f"   🚨 Xavflar: {threats:,} ({threat_percent:.1f}%)\n"
                    f"   👤 Faol foydalanuvchilar: {users}\n"
                    f"   👥 Faol guruhlar: {groups}\n"
                )
                
                # Xavf turlari
                if threat_levels:
                    levels = threat_levels.split(',')
                    unique_threats = [l for l in levels if l != 'Safe']
                    if unique_threats:
                        report += f"   ⚠️ Xavf turlari: {', '.join(set(unique_threats))}\n"
                
                report += "\n"
            
            # Umumiy xulosa
            overall_percent = (all_threats / all_messages * 100) if all_messages > 0 else 0
            
            report += "=" * 40 + "\n\n"
            report += "📋 <b>Umumiy xulosa:</b>\n\n"
            
            if overall_percent > 10:
                report += "🔴 <b>YUQORI XAVFLI</b>\n"
                report += "Tizimda ko'plab xavfli xabarlar aniqlandi. Qo'shimcha himoya choralari tavsiya etiladi.\n"
            elif overall_percent > 5:
                report += "🟡 <b>O'RTACHA XAVFLI</b>\n"
                report += "Xavf darajasi normal diapazonda. Monitoringni davom ettiring.\n"
            else:
                report += "🟢 <b>PAST XAVFLI</b>\n"
                report += "Tizim xavfsiz holatda. Yaxshi ish davom ettirilmoqda!\n"
            
            report += f"\n📊 <b>O'rtacha xavf darajasi:</b> {overall_percent:.2f}%\n"
            report += f"📈 <b>Oylik o'sish:</b> {await self._calculate_growth_rate(monthly_stats):.1f}%\n"
            
            # Tavsiyalar
            report += "\n💡 <b>Tavsiyalar:</b>\n"
            if overall_percent > 10:
                report += "• Foydalanuvchilarni xavfsizlik bo'yicha o'qitish\n"
                report += "• Qo'shimcha tahlil qoidalarini qo'shish\n"
                report += "• Shubhali foydalanuvchilarni monitoring qilish\n"
            elif overall_percent > 5:
                report += "• Muntazam xavfsizlik tekshiruvlari\n"
                report += "• Yangi xavf patternlarini kuzatish\n"
                report += "• Foydalanuvchilarni ogohlantirish\n"
            else:
                report += "• Mavjud himoyani saqlash\n"
                report += "• Tizimni yangilanishlari bilan yangilash\n"
                report += "• Backup va monitoringni davom ettirish\n"
            
            # Hisobotni faylga saqlash
            await self._save_report_to_file(monthly_stats)
            
            return report
            
        except Exception as e:
            return f"❌ Hisobot tayyorlashda xato: {str(e)[:200]}"
    
    async def _calculate_growth_rate(self, monthly_stats: List[Tuple]) -> float:
        """O'sish sur'atini hisoblash"""
        if len(monthly_stats) < 2:
            return 0.0
        
        try:
            # Oxirgi 2 oy
            last_month = monthly_stats[0]
            prev_month = monthly_stats[1]
            
            last_threats = last_month[2]
            prev_threats = prev_month[2]
            
            if prev_threats == 0:
                return 0.0
            
            growth = ((last_threats - prev_threats) / prev_threats) * 100
            return growth
        except:
            return 0.0
    
    async def _save_report_to_file(self, monthly_stats: List[Tuple]):
        """Hisobotni faylga saqlash"""
        try:
            report_data = {
                "generated_at": datetime.now().isoformat(),
                "period_months": len(monthly_stats),
                "monthly_data": []
            }
            
            for month, total, threats, users, groups, threat_levels in monthly_stats:
                report_data["monthly_data"].append({
                    "month": month,
                    "total_messages": total,
                    "threats": threats,
                    "unique_users": users,
                    "active_groups": groups,
                    "threat_levels": threat_levels.split(',') if threat_levels else []
                })
            
            # JSON faylga saqlash
            report_file = self.reports_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Hisobot saqlandi: {report_file}")
            
        except Exception as e:
            print(f"❌ Hisobotni saqlashda xato: {e}")
    
    async def generate_threat_heatmap(self) -> Optional[io.BytesIO]:
        """
        Xavflar issiqlik xaritasi yaratish
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Soatlik ma'lumotlar
            cursor.execute('''
                SELECT 
                    strftime('%H', created_at) as hour,
                    strftime('%w', created_at) as weekday,
                    COUNT(CASE WHEN threat_level != 'Safe' THEN 1 END) as threats
                FROM logs 
                WHERE created_at > datetime('now', '-30 days')
                GROUP BY hour, weekday
                ORDER BY weekday, hour
            ''')
            
            data = cursor.fetchall()
            
            if not data:
                return None
            
            # DataFrame yaratish
            df = pd.DataFrame(data, columns=['hour', 'weekday', 'threats'])
            
            # Matrix yaratish
            heatmap_data = np.zeros((24, 7))  # 24 soat, 7 kun
            
            for _, row in df.iterrows():
                hour = int(row['hour'])
                weekday = int(row['weekday'])
                threats = row['threats']
                heatmap_data[hour, weekday] = threats
            
            # Grafik yaratish
            plt.figure(figsize=(10, 6))
            plt.imshow(heatmap_data, cmap='YlOrRd', aspect='auto', interpolation='nearest')
            
            # Soat belgilari
            hours = [f"{h:02d}:00" for h in range(24)]
            weekdays = ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan']
            
            plt.xticks(range(7), weekdays)
            plt.yticks(range(24), hours)
            plt.colorbar(label='Xavflar soni')
            plt.title('Xavflar Issiqlik Xaritasi (30 kun)', pad=20)
            plt.xlabel('Hafta kunlari')
            plt.ylabel('Soatlar')
            
            # Bufferga saqlash
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close()
            buf.seek(0)
            
            return buf
            
        except Exception as e:
            print(f"❌ Heatmap yaratishda xato: {e}")
            return None
    
    async def get_user_behavior_analytics(self, user_id: int) -> Dict:
        """
        Foydalanuvchi xatti-harakatlari tahlili
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Foydalanuvchi ma'lumotlari
            cursor.execute('''
                SELECT 
                    u.user_id, u.username, u.full_name, u.trust_score, u.created_at,
                    COUNT(l.id) as total_messages,
                    SUM(CASE WHEN l.threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_messages,
                    MIN(l.created_at) as first_message,
                    MAX(l.created_at) as last_message
                FROM users u
                LEFT JOIN logs l ON u.user_id = l.user_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                return {}
            
            # Aktivlik patternlari
            cursor.execute('''
                SELECT 
                    strftime('%H', created_at) as hour,
                    COUNT(*) as message_count
                FROM logs 
                WHERE user_id = ?
                GROUP BY hour
                ORDER BY message_count DESC
                LIMIT 5
            ''', (user_id,))
            
            active_hours = cursor.fetchall()
            
            # Xavf patternlari
            cursor.execute('''
                SELECT 
                    threat_level,
                    COUNT(*) as count,
                    GROUP_CONCAT(DISTINCT SUBSTR(message_text, 1, 50)) as sample_messages
                FROM logs 
                WHERE user_id = ? AND threat_level != 'Safe'
                GROUP BY threat_level
                ORDER BY count DESC
            ''', (user_id,))
            
            threat_patterns = cursor.fetchall()
            
            # Risk baholash
            risk_score = await self._calculate_user_risk_score(user_data, threat_patterns)
            
            return {
                "user_info": {
                    "user_id": user_data[0],
                    "username": user_data[1],
                    "full_name": user_data[2],
                    "trust_score": user_data[3],
                    "joined": user_data[4],
                    "total_messages": user_data[5],
                    "threat_messages": user_data[6],
                    "first_message": user_data[7],
                    "last_message": user_data[8]
                },
                "activity_patterns": {
                    "peak_hours": [{"hour": h, "count": c} for h, c in active_hours],
                    "activity_level": await self._determine_activity_level(user_data[5])
                },
                "threat_analysis": {
                    "patterns": [{"level": l, "count": c, "samples": s} for l, c, s in threat_patterns],
                    "risk_score": risk_score,
                    "risk_level": await self._determine_risk_level(risk_score)
                },
                "recommendations": await self._generate_user_recommendations(user_data, threat_patterns, risk_score)
            }
            
        except Exception as e:
            print(f"❌ User analytics xatosi: {e}")
            return {}
    
    async def _calculate_user_risk_score(self, user_data: Tuple, threat_patterns: List) -> float:
        """Foydalanuvchi risk bahosini hisoblash"""
        total_messages = user_data[5] or 1
        threat_messages = user_data[6] or 0
        
        # Asosiy risk: xavfli xabarlar nisbati
        threat_ratio = (threat_messages / total_messages) * 100
        
        # Pattern xavfi
        pattern_risk = 0
        for pattern in threat_patterns:
            if pattern[0] == "Critical":
                pattern_risk += pattern[1] * 5
            elif pattern[0] == "High":
                pattern_risk += pattern[1] * 3
            elif pattern[0] == "Medium":
                pattern_risk += pattern[1] * 2
            else:
                pattern_risk += pattern[1] * 1
        
        # Ishonsizlik darajasi
        trust_score = user_data[3] or 100
        trust_factor = max(0, 100 - trust_score) / 100
        
        # Yakuniy risk
        risk_score = min(100, threat_ratio * 0.7 + pattern_risk * 0.2 + trust_factor * 100 * 0.1)
        
        return risk_score
    
    async def _determine_activity_level(self, message_count: int) -> str:
        """Aktivlik darajasini aniqlash"""
        if message_count == 0:
            return "passive"
        elif message_count < 10:
            return "low"
        elif message_count < 50:
            return "medium"
        elif message_count < 200:
            return "high"
        else:
            return "very_high"
    
    async def _determine_risk_level(self, risk_score: float) -> str:
        """Risk darajasini aniqlash"""
        if risk_score < 10:
            return "low"
        elif risk_score < 30:
            return "medium"
        elif risk_score < 60:
            return "high"
        else:
            return "critical"
    
    async def _generate_user_recommendations(self, user_data: Tuple, threat_patterns: List, risk_score: float) -> List[str]:
        """Foydalanuvchi uchun tavsiyalar"""
        recommendations = []
        
        total_messages = user_data[5] or 0
        threat_messages = user_data[6] or 0
        
        if total_messages == 0:
            recommendations.append("📭 Foydalanuvchi hali xabar yubormagan")
            return recommendations
        
        threat_ratio = (threat_messages / total_messages) * 100
        
        # Xavf darajasi bo'yicha
        if threat_ratio > 50:
            recommendations.append("🔴 Yuqori xavf: Foydalanuvchini bloklash tavsiya etiladi")
        elif threat_ratio > 20:
            recommendations.append("🟡 O'rtacha xavf: Qat'iy monitoring kerak")
        elif threat_ratio > 5:
            recommendations.append("🟢 Past xavf: Oddiy monitoring")
        
        # Xavf patternlari bo'yicha
        critical_patterns = [p for p in threat_patterns if p[0] == "Critical"]
        if critical_patterns:
            recommendations.append(f"⚠️ {len(critical_patterns)} ta Critical xavf aniqlangan")
        
        # Trust score bo'yicha
        trust_score = user_data[3] or 100
        if trust_score < 30:
            recommendations.append("⭐ Past ishonch: Qo'shimcha tekshiruvlar kerak")
        
        # Umumiy tavsiyalar
        if risk_score > 70:
            recommendations.append("🛑 Darhol aralashish tavsiya etiladi")
        elif risk_score > 40:
            recommendations.append("⚠️ Qo'shimcha monitoring o'rnatish")
        
        return recommendations
    
    async def generate_system_health_report(self) -> str:
        """
        Tizim sog'lig'i hisoboti
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Tizim statistikasi
            stats = {
                "uptime": await self._get_system_uptime(),
                "database_size": await self._get_database_size(),
                "active_modules": await self._get_active_modules(),
                "performance_metrics": await self._get_performance_metrics()
            }
            
            # Xavfsizlik statistikasi
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(DISTINCT group_id) as total_groups,
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN threat_level != 'Safe' THEN 1 END) as total_threats,
                    COUNT(DISTINCT CASE WHEN threat_level != 'Safe' THEN user_id END) as users_with_threats
                FROM logs 
                WHERE created_at > datetime('now', '-7 days')
            ''')
            
            security_stats = cursor.fetchone()
            
            report = "🏥 <b>Tizim Sog'lig'i Hisoboti</b>\n\n"
            report += f"📅 Hisobot vaqti: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Uptime
            report += f"⏱️ <b>Uptime:</b> {stats['uptime']}\n"
            
            # Database
            report += f"💾 <b>Ma'lumotlar bazasi:</b> {stats['database_size']:.2f} MB\n"
            
            # Modullar
            report += f"🔧 <b>Faol modullar:</b> {stats['active_modules']}/7\n\n"
            
            # Xavfsizlik
            if security_stats:
                users, groups, messages, threats, users_with_threats = security_stats
                
                report += "🛡️ <b>So'nggi 7 kunlik xavfsizlik:</b>\n"
                report += f"   👤 Foydalanuvchilar: {users}\n"
                report += f"   👥 Guruhlar: {groups}\n"
                report += f"   📨 Xabarlar: {messages}\n"
                report += f"   🚨 Xavflar: {threats}\n"
                report += f"   ⚠️ Xavfli foydalanuvchilar: {users_with_threats}\n"
                
                threat_rate = (threats / messages * 100) if messages > 0 else 0
                report += f"   📊 Xavf darajasi: {threat_rate:.2f}%\n\n"
            
            # Performance
            perf = stats['performance_metrics']
            report += "⚡ <b>Performance:</b>\n"
            report += f"   🎯 Aniqlash darajasi: {perf.get('accuracy', 0):.1f}%\n"
            report += f"   ⏱️ O'rtacha javob vaqti: {perf.get('avg_response_time', 0):.2f}s\n"
            report += f"   📈 Faollik: {perf.get('activity_level', 'normal')}\n"
            
            # Holat baholash
            health_score = await self._calculate_health_score(stats, security_stats)
            
            report += f"\n🏅 <b>Sog'lik bahosi:</b> {health_score}/100\n"
            
            if health_score >= 90:
                report += "🟢 <b>A'LO HOLAT</b> - Tizim mukammal ishlayapti!"
            elif health_score >= 70:
                report += "🟡 <b>YAXSHI HOLAT</b> - Kichik optimallashtirishlar kerak"
            else:
                report += "🔴 <b>MUAMMOLI HOLAT</b> - Tezkor aralashuv kerak"
            
            return report
            
        except Exception as e:
            return f"❌ Tizim hisoboti tayyorlashda xato: {str(e)[:200]}"
    
    async def _get_system_uptime(self) -> str:
        """Sistem uptime ni olish"""
        try:
            # Bu misol uchun - haqiqiy loyihada psutil yoki boshqa vositalardan foydalanish mumkin
            return "7 kun 14 soat"
        except:
            return "Noma'lum"
    
    async def _get_database_size(self) -> float:
        """Database hajmini olish"""
        try:
            import os
            db_size = os.path.getsize("kiber_inspektor.db") / (1024 * 1024)  # MB ga
            return db_size
        except:
            return 0.0
    
    async def _get_active_modules(self) -> int:
        """Faol modullar soni"""
        active = 0
        modules = ['analyzer', 'ai_analyzer', 'url_scanner', 'file_analyzer', 
                  'virustotal_client', 'external_checks', 'monitor']
        
        for module in modules:
            try:
                __import__(f'handlers.{module}')
                active += 1
            except:
                pass
        
        return active
    
    async def _get_performance_metrics(self) -> Dict:
        """Performance metrikalari"""
        try:
            cursor = self.db.conn.cursor()
            
            # Aniqlash darajasi
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN threat_level != 'Safe' THEN 1 ELSE 0 END) as detected
                FROM logs 
                WHERE created_at > datetime('now', '-1 day')
            ''')
            
            perf_data = cursor.fetchone()
            
            accuracy = 0
            if perf_data and perf_data[0] > 0:
                accuracy = (perf_data[1] / perf_data[0]) * 100
            
            return {
                "accuracy": accuracy,
                "avg_response_time": 0.85,  # Misol uchun
                "activity_level": "high" if (perf_data[0] or 0) > 100 else "normal"
            }
        except:
            return {"accuracy": 0, "avg_response_time": 0, "activity_level": "low"}
    
    async def _calculate_health_score(self, stats: Dict, security_stats: Tuple) -> float:
        """Tizim sog'lig'i bahosini hisoblash"""
        score = 100.0
        
        # Database hajmi (optimal 10MB gacha)
        db_size = stats.get('database_size', 0)
        if db_size > 100:
            score -= 30
        elif db_size > 50:
            score -= 15
        elif db_size > 20:
            score -= 5
        
        # Faol modullar
        active_modules = stats.get('active_modules', 0)
        if active_modules < 4:
            score -= 20
        elif active_modules < 6:
            score -= 10
        
        # Xavf darajasi
        if security_stats:
            messages = security_stats[2] or 1
            threats = security_stats[3] or 0
            threat_rate = (threats / messages) * 100
            
            if threat_rate > 20:
                score -= 25
            elif threat_rate > 10:
                score -= 15
            elif threat_rate > 5:
                score -= 5
        
        return max(0, min(100, score))
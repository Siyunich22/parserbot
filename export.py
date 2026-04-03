import pandas as pd
from pathlib import Path
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from database import Company
from logger import setup_logger
from config import EXPORT_DIR

logger = setup_logger("export")

class ExportManager:
    """Менеджер экспорта данных"""
    
    def __init__(self):
        self.export_dir = EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def export_to_csv(self, companies: List[Company], filename: str = None) -> Path:
        """Экспортировать в CSV"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = self.export_dir / filename
        
        data = []
        for company in companies:
            data.append({
                'Название': company.name,
                'Телефон': company.phone or '',
                'Email': company.email or '',
                'Веб-сайт': company.website or '',
                'Адрес': company.address or '',
                'Город': company.city or '',
                'Категория': company.category or '',
                'Рейтинг': company.rating or '',
                'Источник': company.source,
                'Ссылка': company.source_url or '',
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig', sep=',')
        
        logger.info(f"Экспортировано {len(companies)} компаний в {filename}")
        return filepath
    
    def export_to_excel(self, companies: List[Company], filename: str = None) -> Path:
        """Экспортировать в Excel"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        filepath = self.export_dir / filename
        
        data = []
        for company in companies:
            data.append({
                'Название': company.name,
                'Телефон': company.phone or '',
                'Email': company.email or '',
                'Веб-сайт': company.website or '',
                'Адрес': company.address or '',
                'Город': company.city or '',
                'Категория': company.category or '',
                'Рейтинг': company.rating or '',
                'Источник': company.source,
                'Ссылка': company.source_url or '',
                'Дата обновления': company.last_updated.isoformat() if company.last_updated else '',
            })
        
        df = pd.DataFrame(data)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Контакты', index=False)
            
            # Форматирование
            worksheet = writer.sheets['Контакты']
            for column in worksheet.columns:
                max_length = 0
                column = [cell for cell in column]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
        
        logger.info(f"Экспортировано {len(companies)} компаний в {filename}")
        return filepath
    
    def get_export_path(self, filename: str) -> Path:
        """Получить полный путь к экспорту"""
        return self.export_dir / filename

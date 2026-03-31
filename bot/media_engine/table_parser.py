"""Pandas + openpyxl — парсинг Excel/CSV таблиц.

Нормализация данных, валидация структуры.
"""

from __future__ import annotations

import io
import time

import structlog

logger = structlog.get_logger()


async def parse_table(
    file_data: bytes,
    filename: str,
) -> dict:
    """Parse Excel or CSV file.

    Returns dict with:
        - text: human-readable summary
        - rows: number of rows
        - columns: list of column names
        - preview: first 10 rows as text
        - data: list of dicts (if small enough)
    """
    start = time.monotonic()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        import pandas as pd

        if ext == "csv":
            # Try different encodings
            for encoding in ("utf-8", "cp1251", "latin1"):
                try:
                    df = pd.read_csv(io.BytesIO(file_data), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return {"text": "Не удалось определить кодировку CSV файла."}
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(file_data))
        else:
            return {"text": f"Неподдерживаемый формат таблицы: {ext}"}

        elapsed = time.monotonic() - start

        # Build result
        columns = list(df.columns)
        rows = len(df)
        preview = df.head(10).to_string(index=False)

        # Summary
        summary_parts = [
            f"📊 <b>Таблица: {filename}</b>",
            f"Строк: {rows}, Столбцов: {len(columns)}",
            f"Столбцы: {', '.join(str(c) for c in columns[:10])}",
        ]

        # Numeric column stats
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            summary_parts.append("\nСтатистика:")
            for col in numeric_cols[:5]:
                summary_parts.append(
                    f"  {col}: мин={df[col].min()}, макс={df[col].max()}, "
                    f"сумма={df[col].sum():.2f}"
                )

        summary_parts.append(f"\nПревью (первые 10 строк):\n<pre>{preview}</pre>")
        text = "\n".join(summary_parts)

        logger.info(
            "table_parsed",
            filename=filename,
            rows=rows,
            columns=len(columns),
            elapsed_sec=round(elapsed, 2),
        )

        result = {
            "text": text,
            "rows": rows,
            "columns": columns,
            "preview": preview,
        }

        # Include data as list of dicts if small
        if rows <= 100:
            result["data"] = df.to_dict(orient="records")

        return result

    except ImportError:
        logger.warning("pandas_not_installed")
        return {"text": "Pandas не установлен. Установи: pip install pandas openpyxl"}
    except Exception as e:
        logger.error("table_parse_error", error=str(e), filename=filename)
        return {"text": f"Ошибка при обработке таблицы: {e}"}

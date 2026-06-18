"""ParserStrategy реализации для SETUP-04."""

from fe_bot.setup.parser.strategies.csv_parser import CSVParserStrategy
from fe_bot.setup.parser.strategies.docx_parser import DOCXParserStrategy
from fe_bot.setup.parser.strategies.json_parser import JSONParserStrategy
from fe_bot.setup.parser.strategies.markdown import MarkdownParserStrategy
from fe_bot.setup.parser.strategies.pdf_parser import PDFParserStrategy
from fe_bot.setup.parser.strategies.plain_text import PlainTextParserStrategy
from fe_bot.setup.parser.strategies.xlsx_parser import XLSXParserStrategy

__all__ = [
    "CSVParserStrategy",
    "DOCXParserStrategy",
    "JSONParserStrategy",
    "MarkdownParserStrategy",
    "PDFParserStrategy",
    "PlainTextParserStrategy",
    "XLSXParserStrategy",
]

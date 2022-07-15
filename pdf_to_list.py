import pdfplumber
from pdfplumber.utils import cluster_objects
from pdfplumber.utils import collate_line as base_collate_line
from pdfplumber.utils import DEFAULT_Y_TOLERANCE, DEFAULT_X_TOLERANCE
from operator import itemgetter
from functools import partial
import PyPDF2
import re

open_bold_tag = "<b>"
close_bold_tag = "</b>"

def get_bold_sentences(text):
    return re.findall(r'<b>(.+?)</b>', text)

def remove_bold_tags(text):
    return re.sub(r'</?b>', '', text)

def btag_collate_line(line_chars,
                      bold_check_func=None,
                      tolerance=DEFAULT_X_TOLERANCE):
    open_bold_tag = "<b>"
    close_bold_tag = "</b>"
    coll = ""
    last_x1 = None
    global bold_sentence
    for char in sorted(line_chars, key=itemgetter("x0")):
        if (last_x1 is not None) and (char["x0"] > (last_x1 + tolerance)):
            coll += " "
        last_x1 = char["x1"]
        if bold_check_func(char):
            if not bold_sentence:
                coll += open_bold_tag
                bold_sentence = True
        else:
            if bold_sentence:
                coll += close_bold_tag
                bold_sentence = False
        coll += char["text"]
    return coll


def extract_text_with_bolds(page, bold_check_func):
    global bold_sentence
    if bold_check_func is None:
        collate_line = partial(
            base_collate_line, tolerance=DEFAULT_X_TOLERANCE)
    else:
        collate_line = partial(
            btag_collate_line, bold_check_func=bold_check_func)
    chars = page.dedupe_chars().chars
    doctop_clusters = cluster_objects(chars, "doctop", DEFAULT_Y_TOLERANCE)
    bold_sentence = False
    lines = [collate_line(line_chars) for line_chars in doctop_clusters]
    if bold_sentence:
        lines[-1] += close_bold_tag
    return "\n".join(lines)

def char_in_tables_vertical(char, tables):
    v_mid = (char["top"] + char["bottom"]) / 2
    for table in tables:
        x0, top, x1, bottom = table.bbox
        in_bbox = (v_mid >= top) and (v_mid < bottom)
        if in_bbox:
            return True
    return False

def quick_extract_pypdf2(pdf_path, clean=True):
    output = ""
    with open(pdf_path, 'rb') as f:
        pdf = PyPDF2.PdfFileReader(f)
        for page in range(pdf.numPages):
            output += pdf.getPage(page).extractText()
    if clean:
        output = re.sub(r'\s+', ' ', output)
    return output

def custom_extract_pdfplumber(pdf_path, bold_check_func, skip_tables, table_settings):
    pdf = pdfplumber.open(pdf_path)
    output = ""
    for page in pdf.pages:
        to_extract = page
        if skip_tables:
            tables = page.find_tables(table_settings)
            if tables:
                to_extract = page.filter(lambda obj: obj["object_type"] == "char"
                                         and not char_in_tables_vertical(obj, tables))
        output += extract_text_with_bolds(to_extract, bold_check_func)
    return output

def get_pdf_content(pdf_path,
                    clean=True,
                    tag_bolds=False,
                    skip_tables=True,
                    bold_rules=['Bold', 'GuardianSansTT-Medium'],
                    bold_check_func=None,
                    table_settings={"edge_min_length": 10}):
    if bold_check_func is None:
        if tag_bolds:
            def bold_check_func(char): return any(
                rule in char['fontname'] for rule in bold_rules)
        elif not skip_tables:
            # si no se necesitan bolds ni saltarse las tablas se
            # usa pypdf2
            return quick_extract_pypdf2(pdf_path, clean=clean)
    pdf = pdfplumber.open(pdf_path)
    output = ""
    for page in pdf.pages:
        to_extract = page
        if skip_tables:
            tables = page.find_tables(table_settings)
            if tables:
                to_extract = page.filter(lambda obj: obj["object_type"] == "char"
                                         and not char_in_tables_vertical(obj, tables))
        output += extract_text_with_bolds(to_extract, bold_check_func)
    if clean:
        output = re.sub(r'\s+', ' ', output)
    return output
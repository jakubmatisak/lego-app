"""Odpovede ECB v tvare, v akom chodia naozaj (skrátené na pár mien a dní).

Denný súbor je XML s jedným dňom, celý rad ZIP s jedným CSV. Kurzy sú
skutočné referenčné kurzy ECB, verejné údaje bez obmedzenia.
"""

import io
import zipfile

DAILY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
\t<gesmes:subject>Reference rates</gesmes:subject>
\t<gesmes:Sender>
\t\t<gesmes:name>European Central Bank</gesmes:name>
\t</gesmes:Sender>
\t<Cube>
\t\t<Cube time='{day}'>
\t\t\t<Cube currency='USD' rate='1.1734'/>
\t\t\t<Cube currency='JPY' rate='173.76'/>
\t\t\t<Cube currency='CZK' rate='24.320'/>
\t\t\t<Cube currency='GBP' rate='0.87310'/>
\t\t\t<Cube currency='HUF' rate='391.68'/>
\t\t\t<Cube currency='PLN' rate='4.2683'/>
\t\t\t<Cube currency='CHF' rate='0.9345'/>
\t\t</Cube>
\t</Cube>
</gesmes:Envelope>
"""

#: Štvrtok 2024-03-14, piatok 2024-03-15, pondelok 2024-03-18; víkend chýba.
HIST_CSV = (
    "Date,USD,JPY,BGN,CYP,CZK,DKK,EEK,GBP,HUF,LTL,LVL,MTL,PLN,ROL,RON,SEK,SIT,SKK,CHF,\n"
    "2024-03-18,1.0872,162.43,1.9558,N/A,25.044,7.4564,N/A,0.85445,394.80,N/A,N/A,N/A,"
    "4.3053,N/A,4.9706,11.2930,N/A,N/A,0.9655,\n"
    "2024-03-15,1.0890,161.69,1.9558,N/A,24.950,7.4570,N/A,0.85458,395.38,N/A,N/A,N/A,"
    "4.2908,N/A,4.9698,11.3460,N/A,N/A,0.9614,\n"
    "2024-03-14,1.0925,161.68,1.9558,N/A,25.081,7.4566,N/A,0.85485,394.11,N/A,N/A,N/A,"
    "4.2913,N/A,4.9700,11.3135,N/A,N/A,0.9616,\n"
    "1999-01-04,1.1789,133.73,N/A,0.58231,35.107,7.4501,15.6466,0.71110,251.48,4.7170,"
    "0.6668,0.4565,4.0712,1.3111,N/A,9.4696,189.0450,42.9910,1.6168,\n"
)


def daily_xml(day: str) -> bytes:
    return DAILY_XML.format(day=day).encode("utf-8")


def hist_zip(csv_text: str = HIST_CSV) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("eurofxref-hist.csv", csv_text)
    return buffer.getvalue()

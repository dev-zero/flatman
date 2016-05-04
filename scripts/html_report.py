#!/usr/bin/python
import os
import numpy as np
import requests

SERVER = 'https://172.23.64.223/fatman'
SERVER = 'http://127.0.0.1:5001'
COMPARE_URL = SERVER + '/compare'
METHODS_URL = SERVER + '/methods'
TESTS_URL = SERVER + '/tests'

headersection = """
<HTML>
<HEAD>
<!--https://css-tricks.com/simple-css-row-column-highlighting/-->
<STYLE>
table {
  overflow: hidden;
}

tr:hover {
  background-color: #ffa;
}

td, th {
  position: relative;
  font-size: 11;
}
td:hover::after,
th:hover::after {
  content: "";
  position: absolute;
  background-color: #ffa;
  left: 0;
  top: -5000px;
  height: 10000px;
  width: 100%;
  z-index: -1;
}
</STYLE>
</HEAD>
<BODY><H1>Method Comparison Matrix</H1>
"""


class deltaReport():
    """ Base Class for reporting Deltatest results """
    def __init__(self, outfile):
        self.outfile = outfile
        self.output = ""
        self.nlines = 0

    def set_report_header(self, code="abinit", subtitle="small text", features=[]):
        self.output = self.get_file_intro() 
        self.output += self.get_method_description(code, subtitle, features)


    def set_table_footer(self, delta_avg=-1., delta_std=-1.):
        self.output += self.get_table_outro(delta_avg, delta_std) 

    def set_report_footer(self):
        self.output += self.get_file_outro() 


    def write(self):
        with open(self.outfile,'w') as of:
            of.write(self.output)



class HTMLReport(deltaReport):
    """Output as fancy HTML table"""
    def __init__(self, outfile):
        deltaReport.__init__(self, outfile)
        self.added_headers = False
        self.added_link_headers = False
        self.columns = 0

    def get_file_intro(self):
        text = r"""<HTML><HEAD>
                         <TITLE>Deltatest Report</TITLE>
                        <script type="text/javascript" src="jquery-latest.js"></script> 
                        <script type="text/javascript" src="jquery.tablesorter.min.js"></script> 
                        <link rel="stylesheet" type="text/css" href="blue/style.css">
                        <SCRIPT type="text/javascript" >
                         $(document).ready(function() 
                            { 
                                $("table").tablesorter( {sortList: [[0,0]]} ); 
                            } 
                        );  
                        </SCRIPT>
                        </HEAD><BODY>
                """
        return text


    def get_method_description(self, code, subtitle, features):
        ncols = len(features)/2+1
        line1 = ""
        line2 = ""

        for f,v in features[::2]:
            line1 += r"<TD> <b>{:s}</b>: {:s} </TD>".format(f,v)
        for f,v in features[1::2]:
            line2 += r"<TD> <b>{:s}</b>: {:s} </TD>".format(f,v)

        text  = r"""<TABLE width="1100px" frame="box" align="center">"""
        text += r"""<TR><TD><font size=4> {:s}</font></TD> {:s}</TR>""".format(code,line1)
        text += r"""<TR><TD>{:s}</TD> {:s}</TR>""".format(subtitle, line2)


        text += r"""</TABLE>"""
        return text

    def add_link(self, url, disp=None):
        if not self.added_link_headers:
            self.add_link_headers()

        if disp is None:
            disp=url
        text = """
                   &nbsp;&nbsp;<A href="{0:s}">{1:s}</A>&nbsp;&nbsp;\n
               """.format(url,disp)
        self.output += text

    def add_link_headers(self):
        text = """
                   <TABLE width="1100px" align="center"><TR><TD>Subgroups:
               """
        self.output += text
        self.added_link_headers = True


    def get_file_outro(self):
        text = r""" </BODY>
                    </HTML>
                    """
        if self.added_link_headers:
            text = "</TD></TR></TABLE>" + text
        return text

    def get_table_outro(self, delta_avg=None, delta_std=None):
        if delta_avg is not None:
            if delta_std is not None:
                avgtext = "<TR style=\"border-top:1px solid;border-bottom:1px solid;\"><TD colspan=\"{:d}\" align=\"right\">Average Delta (n={:2d}):</TD><TD align=\"right\">{:6.3f}</TD><TD align=\"right\">&plusmn; {:6.3f}</TD></TR>".format(self.columns-2, self.nlines, delta_avg,delta_std)   
            else:
                avgtext = "<TR><TD colspan=\"{:d}\" align=\"right\">Average Delta (n={:2d}):</TD><TD> {:6.3f}</TD></TR>".format(self.columns-1, self.nlines, delta_avg)   
        else:
            avgtext = ""

        text = r""" </TBODY>{:s}
                    </TABLE>
                """.format(avgtext)
        return text

    def add_line(self, dataline):
        if self.added_headers == False:
            self.output += self.get_tableheaders(dataline)
            self.added_headers = True
            self.columns = len(dataline)

        self.nlines+=1
        text = "<TR>"
        data = [x[1] for x in dataline]

        for d in data:
            if isinstance(d, float):
                text += "<TD align=\"right\">{:6.3f}</TD>".format(d)
            elif isinstance(d, tuple):
                text += "<TD align=\"right\">{:>2d}, {:>2d}, {:>2d}</TD>".format(d[0], d[1], d[2])
            elif isinstance(d, str):
                text += "<TD align=\"right\">{:s}</TD>".format(d)
            else:
                text += "<TD align=\"right\">{:s}</TD>".format(d)

        text = text[:-1] + "</TR>\n"
        self.output  += text

    def get_tableheaders(self, dataline):
        text = "\n\n <br/> <TABLE width=\"1100px\" align=\"center\" id=\"resultsTable\" class=\"tablesorter\" style=\"border-collapse:collapse;\"> \n<THEAD><TR style=\"border-top:1px solid;border-bottom:1px solid;\">"
        keys = [x[0] for x in dataline]

        for k in keys:
            text += "<TH align=\"right\"><b>{:s}</b></TH>".format(k)

        text = text + "</TR></THEAD><TBODY> \n"
        return text


def create_html_comparison():
    """make a bunch of comparative html outputs"""
    elements =  { "H":1, "He":2, "Li":3, "Be":4, "B":5, "C":6, "N":7, "O":8, "F":9, "Ne":10, "Na":11, "Mg":12, "Al":13, "Si":14, "P":15, "S":16, "Cl":17, "Ar":18, "K":19, "Ca":20, "Sc":21, "Ti":22, "V":23, "Cr":24, "Mn":25, "Fe":26, "Co":27, "Ni":28, "Cu":29, "Zn":30, "Ga":31, "Ge":32, "As":33, "Se":34, "Br":35, "Kr":36, "Rb":37, "Sr":38, "Y":39, "Zr":40, "Nb":41, "Mo":42, "Tc":43, "Ru":44, "Rh":45, "Pd":46, "Ag":47, "Cd":48, "In":49, "Sn":50, "Sb":51,  "Te":52, "I":53, "Xe":54, "Cs":55, "Ba":56, "Hf":72, "Ta":73, "W":74, "Re":75, "Os":76, "Ir":77, "Pt":78, "Au":79, "Hg":80, "Tl":81, "Pb":82, "Bi":83,  "Po":84, "Rn":86 }

    req = requests.get(METHODS_URL, verify = False)
    req.raise_for_status()
    method_list = sorted(req.json(), key = lambda x:x[0])

    of = open("/users/ralph/work/fatman/reports/html/index.html","w")
    of.write(headersection)
    of.write("<TABLE><TR><TD style=\"width:40px\"></TD>")
    of.write("".join(["<TD style=\"width:40px\"><span title=\"{:}\">{:}</span></TD>".format(x[1],x[0]) for x  in method_list]))
    of.write("</TR>\n")

    for m_id_1, desc_1 in method_list:
        of.write("<TR style=\"hover {{background: yellow;}}\"><TD><span title=\"{:}\">{:}</span></TD>".format(desc_1,m_id_1))

        for m_id_2, desc_2 in method_list:
            if m_id_2<=m_id_1 :
                of.write("<TD></TD>")
                continue
            print m_id_1, m_id_2
            req = requests.get(COMPARE_URL, params = {"method1": m_id_1, "method2": m_id_2} , verify = False)

            req.raise_for_status()
            a = req.json()
            val = a["summary"]["avg"]
            if val>99:
                of.write("<TD><a href={:} title=\"avg: {:}\n std: {:}\n n: {:}\">&gt;99</a></TD>".format("{:04d}-{:04d}.html".format(m_id_1, m_id_2),val,a["summary"]["stdev"],a["summary"]["N"]))
            elif str(val)=='nan':
                of.write("<TD></TD>")
                continue
            else:
                of.write("<TD><a href={:} title=\"avg: {:}\n std: {:}\n n: {:}\">{:3.2f}</a></TD>".format("{:04d}-{:04d}.html".format(m_id_1, m_id_2),val,a["summary"]["stdev"],a["summary"]["N"], val ))

            detailreport = HTMLReport("/users/ralph/work/fatman/reports/html/{:04d}-{:04d}.html".format(m_id_1, m_id_2))
            detailreport.set_report_header(code=desc_1, subtitle=desc_2, features=[])
            #detailreport.
            for t, line in a["test"].items():
                if "deltatest_" in t:
                    element = t.replace("deltatest_","")

                dataline = [("z", str(elements[element])),
                            ("Element", element), 
                            ("V<sub>0</sub>", line[0]), 
                            ("B<sub>0</sub>", line[1]),  
                            ("B<sub>1</sub>", line[2]), 
                            ("V<sub>0,r</sub>", line[3]), 
                            ("B<sub>0,r</sub>", line[4]),  
                            ("B<sub>1,r</sub>", line[5]), 
                            ("&Delta;",         line[6]) ]
                detailreport.add_line(dataline)

            detailreport.set_table_footer(delta_avg = a["summary"]["avg"], delta_std=a["summary"]["stdev"])
            detailreport.write()
        of.write("</TR>")


    of.write("</TABLE>")
    of.write("</BODY></HTML>")
    of.close()









    req = requests.get(TESTS_URL, verify = False)
    req.raise_for_status()
    test_list = sorted(req.json(), key = lambda x:x[0])

    of = open("/users/ralph/work/fatman/reports/html-by-test/index.html","w")
    of.write(headersection)
    of.write("<TABLE><TR><TD style=\"width:40px\"></TD>")
    of.write("".join(["<TD style=\"width:40px\"><span title=\"{:}\">{:}</span></TD>".format(x[1],x[0]) for x  in method_list]))
    of.write("</TR>\n")

    for t_id_1, desc_1 in test_list:
        if not 'deltatest' in desc_1: continue
        of.write("<TR style=\"hover {{background: yellow;}}\"><TD>{:}</TD>".format(desc_1))

        detailreport = HTMLReport("/users/ralph/work/fatman/reports/html-by-test/{:}.html".format(desc_1))
        detailreport.set_report_header(code=desc_1, subtitle="Reference V0 = {:}, B0 = {:}, B1 = {:}", features=[])

        for m_id_2, desc_2 in method_list:
           #if m_id_2<=m_id_1 :
           #    of.write("<TD></TD>")
           #    continue
            print desc_1, m_id_2
            req = requests.get(COMPARE_URL, params = {"method1": m_id_2, "method2": 3, "test": desc_1} , verify = False)
            req.raise_for_status()
            a = req.json()
            val = a["summary"]["avg"]
            if val>99:
                of.write("<TD><a href={:}.html>&gt;99</a></TD>".format(desc_1))
            elif str(val)=='nan':
                of.write("<TD></TD>")
                continue
            else:
                of.write("<TD><a href={:}.html>{:3.2f}</a></TD>".format(desc_1,val))

            #detailreport.
            for t, line in a["test"].items():
                if "deltatest_" in t:
                    element = t.replace("deltatest_","")
                theid = desc_2.split(",")[0].split(":")[-1]
                dataline = [#("z", str(elements[element])),
                            ("ID", theid        ),
                           #("Element", element), 
                            ("Method", desc_2), 
                            ("V<sub>0</sub>", line[0]), 
                            ("B<sub>0</sub>", line[1]),  
                            ("B<sub>1</sub>", line[2]), 
                           #("V<sub>0,r</sub>", line[3]), 
                           #("B<sub>0,r</sub>", line[4]),  
                           #("B<sub>1,r</sub>", line[5]), 
                            ("&Delta;",         line[6]) ]
                detailreport.add_line(dataline)

        detailreport.set_table_footer(delta_avg = 0., delta_std=0.)
        detailreport.write()
        of.write("</TR>")


    of.write("</TABLE>")
    of.write("</BODY></HTML>")
    of.close()

if __name__ == "__main__":
    create_html_comparison()



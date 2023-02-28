############################################
# Determines how to open a docx or odt file
# and convert its contents to xhtml
#
from odf.odf2xhtml import ODF2XHTML, special_styles
from odf.namespaces import *
from bs4 import BeautifulSoup
import mammoth
import os, sys
from parsing_libraries import HTML_PARSER
class SimpleODF2XHTML(ODF2XHTML):
    """
    Modifying ODF2XHTML so that it doesn't keep any css and also need to change the way it does a few things
    """
    def __init__(self, generate_css=False, embedable=False):
        super().__init__(generate_css, embedable)
        self.elements[(TEXTNS, 'deletion')] = (self.s_ignorexml, None)
        self.elements[(TEXTNS, 'span')] = (self.s_text_span_convert, self.e_text_span_convert)

    def e_text_note_body(self, tag, attrs):
        """
        Hacked to make it not write out the opening and closing p tag
        Note: multi-paragraph footnotes not currently supported, and will be forced
        to one paragraph.
        """
        self._wfunc = self._orgwfunc
        #my code
        #remove p tags because we need to put stuff before ending p tag
        #useless spans are occasionally in there too, seems to happen in files converted from docx
        self.notebody = [i for i in self.notebody if i not in ['<p>', '</p>', '<span>', '</span>']]
        #end my code
        self.notedict[self.currentnote]['body'] = ''.join(self.notebody)
        self.notebody = ''
        del self._orgwfunc

    def e_text_note_citation(self, tag, attrs):
        """
        Hacked so that sup tags come first before a tag and also so that the text is enclosed in brackets
        """
        mark = ''.join(self.data)
        self.notedict[self.currentnote]['citation'] = mark
        self.opentag('sup')
        self.opentag('a',{ 'href': "#footnote-%s" % self.currentnote , 'id' : "footnote-ref-%s" % self.currentnote})
        # Since HTML only knows about endnotes, there is too much risk that the
        # marker is reused in the source. Therefore we force numeric markers
        if sys.version_info[0]==3:
            self.writeout("[%s]" % str(self.currentnote))
        else:
            self.writeout(unicode(self.currentnote))
        self.closetag('a')
        self.closetag('sup')
    def generate_footnotes(self):
        """
        Hacked so that footnotes include a reference to go back to where it is referenced
        """
        if self.currentnote == 0:
            return
        if self.generate_css:
            self.opentag('ol', {'style':'border-top: 1px solid black'}, True)
        else:
            self.opentag('ol')
        for key in range(1,self.currentnote+1):
            note = self.notedict[key]
            self.opentag('li', { 'id':"footnote-%d" % key })
            self.opentag('p')
            self.writeout(note['body'])
            self.opentag('a', {'href': "#footnote-ref-%s" % key})
            self.writeout('↑')
            self.closetag('a')
            self.closetag('p')
            self.closetag('li')
        self.closetag('ol')
    def xhtml(self):
        """ Returns the xhtml
        This was broken so I had to hack it.
        If there were footnotes in the document, self.lines would have integers in it
        and then join would crash the program because it only takes strings
        """
        self.lines = [str(i) for i in self.lines]
        xhtml = ''.join(self.lines).encode('us-ascii','xmlcharrefreplace').decode('utf-8')
        #html.unescape('&#1086;&#1087;&#1072;')
        #return ''.join(self.lines)
        return xhtml

    def s_text_span_convert(self, tag, attrs):
        """ 
        This will change text:span to em or strong tags, replacing the existing method in base class.
        If it cannot figure out whether it is bold or italic, it will instead just make it a span tag.
        If it is both, it will create an em tag inside a strong tag.
        """
        self.writedata()
        tag = 'span'
        htmlattrs = {} #not storing them so html will be cleaner and plainer
        is_bold = False
        is_italic = False
        c = attrs.get( (TEXTNS,'style-name'), None)
        if c:
            font_weight, font_style = self.get_font_weight_and_style(c, '.S-')
            item_style = self.styledict.get('.S-%s' %  c, {})
            is_italic = font_style == 'italic'
            is_bold = font_weight == 'bold'
        if(is_bold and is_italic):
            self.opentag('strong', htmlattrs)#add extra tag
            tag = 'em'
        elif(is_italic):
            tag = 'em'
        elif(is_bold):
            tag = 'strong'
        else:
            #span tag, so might need some style TO DO
            #htmlattrs = attrs
            pass
        #not saving formating so spans are useless
        if(tag != 'span'):
            self.opentag(tag, htmlattrs)
        self.purgedata()
    def e_text_span_convert(self, tag, attrs):
        """ 
        This will change text:span to em or strong tags.
        """
        self.writedata()
        tag = 'span'
        htmlattrs = {} #not storing them so html will be cleaner and plainer
        is_bold = False
        is_italic = False
        c = attrs.get( (TEXTNS,'style-name'), None)
        if c:
            font_weight, font_style = self.get_font_weight_and_style(c, '.S-')
            #item_style = self.styledict.get('.S-%s' %  c, {})
            #font_style = item_style.get(('urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0', 'font-style'))
            #font_weight = item_style.get(('urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0', 'font-weight'))
            is_italic = font_style == 'italic'
            is_bold = font_weight == 'bold'
        if(is_bold and is_italic):
            self.closetag('em', htmlattrs)#add extra tag
            tag = 'strong'
        elif(is_italic):
            tag = 'em'
        elif(is_bold):
            tag = 'strong'
        if(tag != 'span'):
           self.closetag(tag, False)
        self.purgedata()
    def s_text_p(self, tag, attrs):
        """ have to look for bold and italic because 
        some p tags might just have that in the css, which we're throwing away
        Note: might be possible to have original s_text_p called in middle so that all this
        code doesn't have to be copied.
        """
        htmlattrs = {}
        #print(attrs)
        specialtag = "p"
        c = attrs.get( (TEXTNS,'style-name'), None)
        font_weight, font_style = '', ''
        if c:
            font_weight, font_style = self.get_font_weight_and_style(c, '.P-')
            c = c.replace(".","_")
            specialtag = special_styles.get("P-"+c)
            if specialtag is None:
                specialtag = 'p'
                if self.generate_css:
                    htmlattrs['class'] = "P-%s" % c
        self.opentag(specialtag, htmlattrs)
        if(font_weight == 'bold'):
            self.opentag('strong', {})
        if(font_style == 'italic'):
            self.opentag('em', {})
        self.purgedata()

    def e_text_p(self, tag, attrs):
        """ End Paragraph
        """
        specialtag = "p"
        c = attrs.get( (TEXTNS,'style-name'), None)
        font_weight, font_style = '', ''
        if c:
            font_weight, font_style = self.get_font_weight_and_style(c, '.P-')
            c = c.replace(".","_")
            specialtag = special_styles.get("P-"+c)
            if specialtag is None:
                specialtag = 'p'
        self.writedata()
        if(font_style == 'italic'):
            self.closetag('em', {})
        if(font_weight == 'bold'):
            self.closetag('strong', {})
        self.closetag(specialtag)
        self.purgedata()
    def get_font_weight_and_style(self, style_name, prefix):
        c = style_name
        item_style = self.styledict.get(prefix +  c, {})
        font_style = item_style.get(('urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0', 'font-style'))
        font_weight = item_style.get(('urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0', 'font-weight'))
        return font_weight, font_style

def open_odt(f_name):
    converter = SimpleODF2XHTML()
    xhtml = converter.odf2xhtml(f_name)
    soup = BeautifulSoup(xhtml, HTML_PARSER)
    headers = soup.find_all('h1')
    #Sometimes the headers are wrapped strangely
    #if you converted from a different file format, for instance
    for h in headers:
        if(hasattr(h, 'a')):
            h.a.extract()#remove a tag
        if(h.parent and h.parent.name == 'li'):
            h.parent.unwrap() #remove li tag
        if(h.parent and h.parent.name == 'ul'):
            h.parent.unwrap() #remove ul tag
    return soup
def open_docx(f_name):
    xhtml = mammoth.convert_to_html(open(f_name, 'rb')).value.encode('us-ascii','xmlcharrefreplace').decode('utf-8')
    soup = BeautifulSoup(xhtml, HTML_PARSER)
    #soup.prettify()
    return soup
def open_file_as_xhtml(f_name):
    """
    Opens file and converts it and returns a BeautifulSoup
    object which can be used to get xhtml
    """
    ext = os.path.splitext(f_name)[-1].lower()
    soup = ''
    if(ext == '.docx'):
        soup = open_docx(f_name)
    elif(ext == '.odt'):
        soup = open_odt(f_name)
    print(soup)
    return soup
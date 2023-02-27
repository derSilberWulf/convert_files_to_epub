import re
from bs4 import BeautifulSoup, NavigableString
FOOTERS = []
FOOTNOTE_DOC_TITLE = 'footnotes.xhtml'
FOOTNOTE_NUM = 0 #footnote numbers need to be changed to be consistent across documents
HTML_PARSER = 'html.parser'
#soup = BeautifulSoup(html_doc, 'html.parser')  (default parser, don't need to specify I don't think)\
#BeautifulSoup(markup, "lxml") --lxml's html parser, specify 'xml' for its xml parser
#BeautifulSoup(markup, "html5lib")  --slow but 'parses the same way a web browser does and creates valid html5 unlike others

def process_html(html_parsed_soup):
    """
    Change html to be neater, etc
    Special notes: Chapters will be divided based on the following: if there are h1 tags, those will be chapter titles, if not then h2, and if no h2, then bold text will be assumed to be chapter titles, and the chapter titles will be used to split the document in split_chapters method
    As a result, if you have no h1 or h2 tags then bold cannot be used for anything else.
    Groups of aesteriks in paragraphs by themselves will be assumed to be story breaks and html classes will be added accordingly.
    """
    #soup = BeautifulSoup(html)
    soup = html_parsed_soup
    if(not isinstance(soup, BeautifulSoup)):
        soup = BeautifulSoup(html_parsed_soup, HTML_PARSER)
    #find asteriks (but only if they're the only thing in the paragraph)
    paragraphs = soup.find_all("p", string=re.compile("^\s*\*+\s*$"))
    for paragraph in paragraphs:
        paragraph['class'] = 'story_break'
    #find chapters
    titles = soup.find_all('h1')
    #No h1 tags? Try h2
    if(len(titles) == 0):
        titles = soup.find_all('h2')
    #still nothing? Try strong tags
    if(len(titles) == 0):
        titles = soup.find_all('strong')
        #process it to remove surrounding p tags and also change strong to h1 tag
        for title in titles:
            title.parent.unwrap()
            title.name = 'h1'
    #Nothing? Give up
    if(len(titles) == 0):
        raise Exception("No section titles/chapters found in the document! Use headers (recommended) or bold text (not recommended).")
    for title in titles:
        title['class'] = 'chapter_title'
    return soup

def process_html_with_blockquotes(html_parsed_soup):
    """
    Find blockquotes marked by [[ and ]] and change them in the html to be blockquote tags
    For example: <p>[[Blockquote in here]]</p> becomes <blockquote><p>Blockquote in here</p></blockquote>
    """
    soup = html_parsed_soup
    if(not isinstance(soup, BeautifulSoup)):
        soup = BeautifulSoup(html_parsed_soup, HTML_PARSER)
    begins = soup.find_all('p', string=re.compile('\[\['))
    endings = soup.find_all('p', string=re.compile('\]\]'))
    #sanity check:
    if(len(begins) != len(endings)):
        raise Exception("Error! unclosed [[ or ]] in document! These are for indicating block quotes!")
    for begin in begins:
        begin.string = begin.string.replace('[[', '')
    for end in endings:
        end.string = end.string.replace(']]', '')
    to_remove = []
    for begin in begins:
        if(begin in endings):
            #single paragraph block quote, and we're done
            begin.wrap(soup.new_tag('blockquote'))
            to_remove.append(begin)
    for i in to_remove:
        begins.remove(i)
        endings.remove(i)
    #now the hard part
    while(len(begins) > 0):
        enclose(soup, begins.pop(0), begins, endings)
    return soup

def enclose(soup, current_begin, begins, ends):
    """
    Helper method for enclosing a group of tags
    """
    elem = next_element(current_begin)
    blockquote = soup.new_tag('blockquote')
    wrap = current_begin.wrap(blockquote)
    
    while(elem not in ends):
        if(elem in begins):
            elem = enclose(soup, begins.pop(0), begins, ends)
        next_e = next_element(elem)
        wrap.append(elem)
        elem = next_e
    wrap.append(elem)
    ends.remove(elem)#not totally necessary
    return wrap

def next_element(elem):
    """
    Helper method for finding next tag after elem (skips NavigableStrings)
    """
    while elem is not None:
        # Find next element, skip NavigableString objects
        elem = elem.next_sibling
        if hasattr(elem, 'name'):
            return elem

def get_doc_title(elem):
    """
    Convenience method for determining the title (contained in h1 tag)
    for an element in the soup tree
    Works whether the document is already split or not
    """
    title = elem.find_previous('h1').string.strip() #should probably have a global variable instead of checking h1 directly
    return slugify(title) + '.xhtml'

def split_chapters(html_parsed_soup):
    """
    Splits html into a list of html
    documents based on h1 tags
    """
    #save and erase footers if they exist
    soup = html_parsed_soup
    if(soup.find(find_footnote_markers)):
        #we have footnotes
        save_footers(soup)
    #split the chapters
    pages = []
    titles = []
    h1tags = soup.find_all('h1')
    for h1tag in h1tags:
        page = [str(h1tag)]
        titles.append(str(h1tag.string).strip())
        elem = next_element(h1tag)
        while elem and elem.name != 'h1':
            page.append(str(elem))
            elem = next_element(elem)
        pages.append(''.join(page))
    return pages
def find_footnote_markers(elem):
    """
    Method to pass to search to help us find sup tags that contain footnote references
    """
    if(elem is None):
        return False
    return hasattr(elem, 'name') and elem.name == 'sup' and hasattr(elem, 'a') and 'footnote' in str(elem.a['href'])

def save_footers(html_parsed_soup):
    """
    Call before splitting the chapters in split_chapers to store footers
    returns a list of strings which should be html ordered lists
    and returns the original string without the footers
    """
    global FOOTNOTE_NUM
    global FOOTERS
    soup = html_parsed_soup
    #find footers and footer references, modify them both, store footers and delete from document
    reg_footer = re.compile('.*footnote.*')
    reg_digit = re.compile('\d+')
    #footnote_markers = soup.find_all('a', href=reg_footer) #note: need to get parent sup tag call .parent on each does it
    footnote_markers = soup.find_all(find_footnote_markers)
    footnotes = soup.find_all('li', id=reg_footer) #use parent to get the whole list ol
    num_offset = FOOTNOTE_NUM #must update this after we are done with last footnote number
    for fm in footnote_markers:
        #change id and href numbers by offset and add footnote document
        href = fm.a['href']
        fm_id = fm.a['id']
        new_href = int(re.search(reg_digit, href).group()) + num_offset
        new_id = int(re.search(reg_digit, fm_id).group()) + num_offset
        fm.a['href'] = FOOTNOTE_DOC_TITLE + re.sub(reg_digit, str(new_href), href)
        fm.a['id'] = re.sub(reg_digit, str(new_id), fm_id)
        fm.a.string = re.sub(str(new_href - num_offset), str(new_href), fm.a.string)
    for fn in footnotes:
        new_id = int(re.search(reg_digit, fn['id']).group()) + num_offset
        new_href = int(re.search(reg_digit, fn.p.a['href']).group()) + num_offset
        fn['id'] = re.sub(reg_digit, str(new_id), fn['id'])
        fn.p.a['href'] = re.sub(reg_digit, str(new_href), fn.p.a['href'])
        href = fn.p.a['href'].replace('#', '')
        follow_link = soup.find('a', id=href)
        title = get_doc_title(follow_link)
        fn.p.a['href'] = title + fn.p.a['href']
        FOOTNOTE_NUM = new_id #this will be updated to the last value so that it works if there are more documents
    #now we remove the footnotes and save them
    to_save_footers = footnotes[0].parent.extract()
    FOOTERS.append(''.join(str(x) for x in to_save_footers.contents))
    return soup, FOOTERS

def restore_footers():
    """
    Returns collected footnotes as an html text
    TODO: switch to fn tags and/or dl and dt, which will require replacing ol and li tags
    """
    footer_html = footers_to_html(FOOTERS)
    soup = str(BeautifulSoup(footer_html, HTML_PARSER))
    return footer_html


def footers_to_html(footers):
    output = '<ol class="footnote_list">'
    for f in footers:
        output = output + f
    output = output + '</ol>'
    return output
    
def get_footer_file_name():
    return FOOTNOTE_DOC_TITLE

def blacklist(html_list, blacklist_titles):
    """
    Given a list of html (strings) and a list of titles (strings)
    remove the html docs whose titles have been specified
    returns the html_list (the same one, not a copy)
    Does nothing if blacklist_titles is empty
    """
    if(len(blacklist_titles) == 0):
        return html_list
    to_remove = []
    for i, html in enumerate(html_list):
        if(get_title_from_html(html) in blacklist_titles):
            to_remove.append(i)
    #remove in reverse order so there is no problem
    for i in reversed(to_remove):
        html_list.pop(i)
    return html_list

def whitelist(html_list, whitelist_titles):
    """
    Given a list of html (strings) and a list of titles (strings)
    keep only the html whose titles have been specified
    returns the html_list (the same one, not a copy)
    Does nothing if whitelist_titles is empty
    """
    #if no titles have been specified, user is not whitelisting, so quit early
    if(len(whitelist_titles) == 0):
        return html_list
    to_remove = []
    for i, html in enumerate(html_list):
        if(get_title_from_html(html) not in whitelist_titles):
            to_remove.append(i)
    #remove in reverse order so there is no problem
    for i in reversed(to_remove):
        html_list.pop(i)
    return html_list

def get_title_from_html(html):
    """
    Get title from a chapter, given the html (should be processed first)
    """
    soup = html
    if(not isinstance(soup, BeautifulSoup)):
        soup = BeautifulSoup(html, HTML_PARSER)
    return str(soup.find('h1').string).strip()
    #return re.search('<h1 class="chapter_title">(.+?)</h1>', html).group(1)

def slugify(value):
    """
    Converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    value = re.sub('[-\s]+', '-', value)
    return value
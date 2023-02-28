import os, sys, re, json, mammoth
from ebooklib import epub
from parsing_libraries import process_html, process_html_with_blockquotes, split_chapters, get_title_from_html, slugify, blacklist, whitelist, restore_footers, get_footer_file_name
from standard_open_files_as_html import open_file_as_xhtml

def safe_read_file(f):
    """
    Safe file open operation that returns the whole file as a string
    Used for opening css files, because most of the rest of the time we do want the program
    to break if a file can't be opened
    returns an empty string if it fails and also prints error message to screen.
    """
    if(f is None):
        #print('No file given')
        return ''
    try:
        data = ''
        with open(f, 'r') as open_f:
            data = open_f.read()
        return data
    except IOError as e:
        print("Couldn't open file: " + f)
        return ''

def process_cmdline():
    """
    The expected input is one data file, which will hold all the paths to the files to use in making the epub
    as well as all the meta data necessary (author, id, title, output file name)
    """
    args = list(sys.argv[1:]) #first argument is program file, so throw it out
    numArgs = len(sys.argv)
    
    if numArgs < 2:
        #try:
        raise Exception("Error: Not enough arguments to command line. One input file is expected. See example input file.")
    elif numArgs > 2:
        raise Exception("Error: Too many arguments on command line. Expected one and only one input file") #maybe someday we'll make multiple files at once, but not today!
    return args[0]

data_file = process_cmdline()
json_data = json.load(open(data_file, 'r')) #everything we need should be in the json file
#change directory to where the json file is because the data will be relative to there
os.chdir(os.path.dirname(data_file))

book = epub.EpubBook()

# set metadata
book.set_identifier(json_data['id'])
#this does not have any other options, so if other ids needed, seems like .add_metadata(NAMESPACE, name, value, others=NONE) will have to be used
book.set_title(json_data['title'])
book.set_language('en')
for author in json_data['authors']:
    #guess file_as if not provided? seems risky
    file_by = author.split(' ')
    last_name = file_by.pop(-1)
    rest_of_name = ' '.join(file_by)
    file_by = last_name + ', ' + rest_of_name
    book.add_author(author, file_as=file_by)

#check for cover image
cover_img = json_data.get('cover_img',None)
cover_page = None
if(not cover_img is None):
    book.set_cover(os.path.basename(cover_img), open(cover_img, 'rb').read())
    cover_page = book.get_item_with_id('cover')
    s_file = json_data.get('cover', None) #TODO replace None with default
    style = safe_read_file(s_file)
    cover_css = epub.EpubItem(uid="style_cover", file_name="style/cover.css", media_type="text/css", content=style)
    book.add_item(cover_css)
    cover_page.add_link(href='style/cover.css', rel='stylesheet', type='text/css')


#change files into html
files = json_data['files']
all_html = []
#titles = []
for f in files:
    #open_file = open(f, 'rb')
    #html_form = mammoth.convert_to_html(open_file).value
    html_form = open_file_as_xhtml(f)
    if(json_data.get('blockquotes_enabled', True)):
        html_form = process_html_with_blockquotes(html_form)
    all_html.extend(split_chapters(process_html(html_form))) #use process_html_with_blockquotes?
    #open_file.close()

#loose html files can be added that will not be in table of contents
intro_loose = []
outro_loose = []
footer_html = restore_footers()
if(cover_page is not None and json_data.get('cover_page_enabled', True)):
    intro_loose.append(cover_page)
def create_html_item(entry):
    content = safe_read_file(entry['file'])
    intro_epub = epub.EpubHtml(title=entry['name'], file_name=entry['name'] + '.' + entry['ext'], lang='en')
    intro_epub.content = content
    
    book.add_item(intro_epub)
    for css in entry.get('css',[]):
        css_content = safe_read_file(css)
        file_name = os.path.basename(css)
        css_epub = epub.EpubItem(uid=file_name, file_name="style/" + file_name, media_type="text/css", content=css_content)
        book.add_item(css_epub)
        intro_epub.add_link(href="style/" + file_name, rel="stylesheet", type="text/css")
    for css in entry.get('defined_css', []):
        intro_epub.add_link(href="style/" + css, rel="stylesheet", type="text/css")
    return intro_epub

if(footer_html):
    footer_epub = epub.EpubHtml(title='footnotes', file_name=get_footer_file_name(), lang='en')
    footer_epub.content = footer_html
    book.add_item(footer_epub)
    outro_loose.append(footer_epub)
    #so we are again just copy and pasting code, which means there is room for improvement...
    #it is a little harder this time though because its slightly different TO DO
    for css in json_data.get('footer_css' , []):
        css_content = safe_read_file(css)
        file_name = os.path.basename(css)
        css_epub = epub.EpubItem(uid=file_name, file_name="style/" + file_name, media_type="text/css", content=css_content)
        book.add_item(css_epub)
        footer_epub.add_link(href="style/" + file_name, rel="stylesheet", type="text/css")
    for css in json_data.get('footer_defined_css', []):
        footer_epub.add_link(href="style/" + css, rel="stylesheet", type="text/css")

for entry in json_data.get('intro_loose_files', []):
    intro_epub = create_html_item(entry)
    intro_loose.append(intro_epub)
for entry in json_data.get('outro_loose_files', []):
    outro_epub = create_html_item(entry)
    outro_loose.append(outro_epub)
    
    
#remove non-whitelisted files (won't do anything if whitelist attribute doesn't exist or is empty)
whitelist(all_html, json_data.get('whitelist', []))
#remove blacklisted files
blacklist(all_html, json_data.get('blacklist', []))

epub_chapters = []
for html in all_html:
    title = get_title_from_html(html)
    c = epub.EpubHtml(title=title, file_name=slugify(title) + '.xhtml', lang='en')
    c.content = html
    book.add_item(c)
    epub_chapters.append(c)


# define Table Of Contents
book.toc = (
             (
                epub.Section('Table of Contents'),
                tuple(epub_chapters)
              ),

            )

# input file has three CSS files: pages.css, content.css, and nav_style.css
# They can be set to null if default ones are not to be used.
#nav style
s_file = json_data.get('nav_css', None) #TODO replace None with check for default from settings file
style = safe_read_file(s_file)
nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
#content style
s_file = json_data.get('content_css', None)
style = safe_read_file(s_file)
content_css = epub.EpubItem(uid="style_content", file_name="style/content.css", media_type="text/css", content=style)
#page style
s_file = json_data.get('pages_css', None)
style = safe_read_file(s_file)
page_css = epub.EpubItem(uid='style_page', file_name='style/pages.css', content=style)
# add CSS file
book.add_item(nav_css)
book.add_item(content_css)
book.add_item(page_css)

# add default NCX and Nav file
e_nav = epub.EpubNav()
e_nav.add_link(href='style/nav.css', rel='stylesheet', type='text/css')
book.add_item(e_nav)
book.add_item(epub.EpubNcx())



for c in epub_chapters:
    c.add_link(href='style/content.css', rel='stylesheet', type='text/css')
    c.add_link(href='style/pages.css', rel='stylesheet', type='text/css')
    #c.add_link(nav_css)
    #add_link(href='styles.css', rel='stylesheet', type='text/css')

# basic spine
book.spine = intro_loose + ['nav'] + epub_chapters + outro_loose

# write to the file
epub.write_epub(json_data['output_file_name'], book, {})
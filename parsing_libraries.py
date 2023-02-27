import re
FOOTERS = []
FOOTNOTE_DOC_TITLE = 'footnotes.xhtml'
def process_html(html):
    """
    Change html to be neater, etc
    Special notes: Chapters will be divided based on the following: bold text will be assumed to
    be the chapter title and a token will be added there to more easily break up chapters in split_chapters.
    As a result, bold cannot be used for anything else.
    Triple aesteriks will be assumed to be story breaks and html classes will be added accordingly.
    """
    #change <p>***</p> to have a class for css formatting
    break_pattern = re.compile('<p>(\*\*\*)</p>', re.S) #make it any number of asteriks?
    html = re.sub(break_pattern, r'<p class="story_break">\1</p>', html)
    #change <p><strong></strong><p> to <p> tags with a chapter_title class
    title_pattern = re.compile('<p><strong>(.+?)</strong></p>', re.S)
    html = re.sub(title_pattern, r'token1234<h2 class="chapter_title">\1</h2>', html) #put in a token before to make it easier to split chapters apart
    #note: one of my works had special subtitles, but this is unlikely to be of general use
    #make body tag have a class "chapter" for formatting
    #html = '<div class="chapter">' + html + '</div>' #divs also not doing anything. epub library must get rid of them I guess.
    return html

def process_html_with_blockquotes(html):
    """
    Change html to be neater, etc
    This option includes the ability to have blockquotes which are marked by double brackets 
    in the work
    For example: [[Blockquote in here]]
    """
    #call original method first
    #it occurs to me, maybe we shouldn't since then we could apply all these optionally
    #html = process_html(html)
    #a certain pattern will designate blockquotes: text surrounded by two brackets. 
    #Since there's no controlling p tags, those will be in there too and must be moved to inside the blockquote tag
    #NOTE: Not sure what this would do if there were multiple blockquotes! Would it be greedy and just take everything in between? How does regex work again?
    blockquote_pattern = re.compile('<p>\[\[(.+?)\]\]</p>', re.S)
    html = re.sub(blockquote_pattern, r'<blockquote><p>\1</p></blockquote>', html)#A blockquote shouldn't be enclosed inside a p tag, right? hmmmm
    return html

def split_chapters(html):
    """
    Splits html into a list of html
    using tokens put in by process_html
    """
    #save and erase footers if they exist
    footers, html = save_footers(html)
    #split
    all_html = html.split('token1234')
    #first token should be right at beginning, so we'll get an empty string, so discard first one
    all_html.pop(0)
    #restore footers
    if(len(footers) > 0):
        #This is for putting all footers at end of chapter, but we now want to
        #put them all together at the end of the whole book, which cannot be done
        #in this method, as it only contains a subset of the footers 
        #thus all we can do is store them for later in global variable
        #for i, h in enumerate(all_html):
        #    all_html[i] = restore_footers(h, footers)
        FOOTERS.extend(footers)
    return all_html

def save_footers(html):
    """
    Call before splitting the chapters in split_chapers to store footers
    returns a list of strings which should be html ordered lists
    and returns the original string without the footers
    """
    footers_pattern = re.compile("<ol>.*?footnote.*?</ol>")
    return split_footers(re.findall(footers_pattern, html)), re.sub(footers_pattern, '', html)

def split_footers(footer_list):
    """
    Helper method to save_footers, which gets li tags because that is what we actually want
    """
    p = re.compile("<li.*?</li>")
    footnotes = []
    for i in footer_list:
        items = re.findall(p, i)
        footnotes.extend(items)
    return footnotes

def restore_footers(html, footers):
    """
    puts the corresponding footer into the right document using the very crude methodology
    of counting footer markers and just assuming everything is in order and getting rid of them
    TODO: switch to fn tags and/or dl and dt, which will require replacing ol and li tags
    """
    footer_count = html.count("#footnote")
    #quit early if there are no footers in this part
    if(footer_count == 0):
        return html
    #we need to find the number in the first footnote marker of this doc to get numbering right
    #it is a number inside brackets inside a sup tag (and there is an a tag too but who cares)
    super_pattern = re.compile('<sup>.*?footnote.*?\[([0-9]*)\].*?</sup>')
    superscripts = re.findall(super_pattern, html)
    #quit early if we get nothing, but this shouldn't happen because of our earlier check so it is likely an error
    if(len(superscripts) == 0):
        #this shouldn't happen because of our earlier check
        print("Error: counted footnotes but didn't parse any. Footnotes detection methodology might be incorrect!")
        return html
    current_start = superscripts[0]

    add_text = '<ol class="footnote_list" start="%s">'.replace("%s", current_start)
    while(footer_count > 0):
        add_text += footers.pop(0)
        footer_count -= 1
    add_text += '</ol>'
    html = html + add_text
    return html

def restore_footers_2(html_list):
    """
    This method is for marking footers placed at the end of the epub book rather than the other
    methodology which places them at the end of each chapter
    As such the footers need to be marked to link across documents
    Also needs to fix the footer references in the html
    This needs to be called externally because parsing_libraries will not have all html at any point
    Edits html_list and returns footers as an html string
    If there are no footnotes, returns None
    """
    #Fix all footers and footnote references so they match up
    footers = FOOTERS
    if(len(footers) < 0):
        return None
    global footer_num 
    footer_num = 0 #will not match up if there are multiple docs so we have to redo it ourselves
    footer_num_footers = 1
    footers_complete = []
    for i, html in enumerate(html_list):
        #footnote_ref_pattern = re.compile('(<sup><a href=")(#footnote-)([0-9]+)(" id="footnote-ref-)([0-9]+)(">\[)([0-9]+)(\]<\/a><\/sup>)', re.S)
        #TODO fix so doesn't collect unrelated sup tags. Need to stop if a </sup> is reached
        footnote_ref_pattern = re.compile('<sup>.+?footnote.+?</sup>', re.S)
        html, num_subs = re.subn(footnote_ref_pattern, lambda exp: footer_2_helper(), html)
        html_list[i] = html
        #now we fix the footers
        file_name = slugify(get_title_from_html(html)) + '.xhtml'
        while(num_subs > 0):
            this_footer = footers.pop(0)
            replacement = r'\g<1>S\g<3>'.replace('S', str(footer_num_footers))
            this_footer = re.sub(r'(<[^>]+?)([0-9]+)(.+?>)', replacement, this_footer)
            replacement = r'\g<1>S\g<2>'.replace('S', file_name)
            this_footer = re.sub(r'(<a[^>]+)(#footnote-ref)', replacement, this_footer)
            footers_complete.append(this_footer)
            num_subs = num_subs - 1
            footer_num_footers = footer_num_footers + 1
    return footers_to_html(footers_complete)
            
        
       

def footer_2_helper():
    """
    Do not call this method
    It will probably be a private method in the future
    """
    global footer_num
    footer_num = footer_num + 1
    #s = r'\1$1\2$2\4$2\6$2\8'.replace('$1', FOOTNOTE_DOC_TITLE).replace('$2', str(footer_num))
    s = r'<sup><a href="1#footnote-2" id="footnote-ref-2">[2]</a></sup>'.replace('1', FOOTNOTE_DOC_TITLE).replace('2', str(footer_num))
    return s

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
    return re.search('<h2 class="chapter_title">(.+?)</h2>', html).group(1)

def slugify(value):
    """
    Converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    value = re.sub('[-\s]+', '-', value)
    return value
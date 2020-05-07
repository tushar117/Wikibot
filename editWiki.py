import pywikibot
import regex as re
from pywikibot.pagegenerators import RandomPageGenerator
import os


class TextColors:
    header='\033[95m'
    endc='\033[0m'
    bold='\033[1m'
    underline='\033[4m'
    class fg:
        lightred='\033[91m'
        lightgreen='\033[92m'
        yellow='\033[93m'
        lightblue='\033[94m'
    class bg: 
        black='\033[40m'
        red='\033[41m'
        green='\033[42m'
        orange='\033[43m'
        blue='\033[44m'
        purple='\033[45m'
        cyan='\033[46m'
        lightgrey='\033[47m'

class EditWikiPages(object):
    def __init__(self, number_mapping, exclude_regex, edit_state_file, edit_msg, \
        max_allowed_edits_per_page=-1, debug=False, highlight_edits=False):
        self.number_mapping = number_mapping
        self.exclude_regex = exclude_regex
        self.cache_file = edit_state_file
        self.digit_pattern = re.compile('[0-9]+')
        self.debug = debug
        self.actual_edited_pages = set()
        self.stats = {
            "total_pages": 0,
            "proposed_page_edits": 0,
            "actual_page_edits": 0,
            "total_word_edits": 0,
            "already_edited": 0, 
            }
        self.edit_msg = edit_msg
        self.max_edits = max_allowed_edits_per_page if max_allowed_edits_per_page > 0 else 1e9 
        self.load_edited_page_titles()
        #use with caution
        self.highlight = highlight_edits
        self.title_color = TextColors.fg.yellow
        self.fg = TextColors.fg.lightred
        self.bg = TextColors.bg.lightgrey

    def editPage(self, page):
        self.stats["total_pages"]+=1
        if page.title(underscore=True) in self.actual_edited_pages:
            self.stats["already_edited"]+=1
            return
        original_text = page.text 
        article_text = page.text
        proposed_editing_area = re.compile('[0-9]+').findall(article_text)
        if len(proposed_editing_area)==0 or len(proposed_editing_area) > self.max_edits:
            return
        self.stats["proposed_page_edits"]+=1
        
        #find editing section of the wikipedia
        edit_counts = 0
        if self.debug:
            #might not work properly on all terminals
            if self.highlight:
                extra_offset=0
                highlighted_text = article_text
                print("--"*30)
                print("page title : %s%s%s" %(self.title_color, page.title(), TextColors.endc))
                print("--"*30)
                exclude_spans = self.get_exclude_span(article_text)
                re_iterator = self.digit_pattern.finditer(article_text)
                for match in re_iterator:
                    start = match.start()
                    end = match.end()
                    if self.is_editing_area(start, end-1, exclude_spans):
                        start+=extra_offset
                        end+=extra_offset
                        extra_offset+=len(self.fg) + len(TextColors.endc) + len(self.bg)
                        highlighted_text = "%s%s%s%s%s"%(highlighted_text[0:start], self.fg, \
                            highlighted_text[start:end], TextColors.endc, highlighted_text[end:])
                print(highlighted_text)
                print("##"*30)
            else:
                print("--"*30)
                print("page title : %s" %page.title())
                print("--"*30)
                print(article_text)
                print("##"*30)

        re_iterator = re.compile('[0-9]+').finditer(article_text)
        for match in re_iterator:
            start = match.start()
            end = match.end()
            exclude_spans = self.get_exclude_span(article_text)
            if self.is_editing_area(start, end-1, exclude_spans):
                status, new_str = self.get_translated_number_string(article_text[start:end])
                if not status:
                    continue
                print("%s#%s#%s"% (article_text[start-50:start], article_text[start:end], article_text[end:end+50]))
                print(">> replacing '%s' with '%s'." % (article_text[start:end], new_str))
                response = input(">> Proceed with proposed edit?: [y]es | [n]o | [a]bort  ")
                if response[0].lower()=='n':
                    continue
                elif response[0].lower()=='a':
                    break
                else:
                    new_article_text = "%s%s%s" % (article_text[0:start], new_str, article_text[end:])
                    title_underscore = page.title(underscore=True)
                    article_text = new_article_text
                    self.write_edited_page_titles(title_underscore)
                    self.actual_edited_pages.add(title_underscore)
                    edit_counts+=1
        
        #finally changing the article
        if original_text != article_text:
            page.text = article_text
            page.save(self.edit_msg)
        
        if edit_counts > 0:
            self.stats["actual_page_edits"]+=1
            self.stats["total_word_edits"]+=edit_counts

    #check whether present text span is allowed for editing
    def is_editing_area(self, start, end, non_editing_area):
        status = True
        for span in non_editing_area:
            if end < span[0] or span[1] < start:
                #non overlapping section
                continue
            else:
                return False
        return status

    #find the non editing section of wikipedia
    def get_exclude_span(self, article_text, show_spans=False):
        exclude_spans=[]
        for regex_name, regex_string in self.exclude_regex.items():
            if self.debug and show_spans:
                print("=="*30)
                print("exluding %s" % regex_name)
                print("=="*30)
            regex = re.compile(regex_string)
            re_iterator = regex.finditer(article_text)
            for match in re_iterator:
                exclude_spans.append([match.start(), match.end()-1])
                if self.debug and show_spans:
                    print("%s"%match.group())
        return exclude_spans

    #its transliterate the number literals according to number_mapping
    def get_translated_number_string(self, number):
        res = ""
        status = True
        for i in number:
            if self.number_mapping.get(i, None) is not None:
                res+=self.number_mapping[i]
            else:
                status = False
                break
        return status, res

    #store the titles 
    def write_edited_page_titles(self, title):
        if title not in self.actual_edited_pages:
            with open(os.path.abspath(self.cache_file), 'a+', encoding='utf-8') as logfile:
                logfile.write("%s\n"%title)
    
    #load the previous store process state file containing edited article's title
    def load_edited_page_titles(self):
        if os.path.exists(self.cache_file) and os.path.isfile(self.cache_file):
            with open(os.path.abspath(self.cache_file), 'r', encoding='utf-8') as logfile:
                for line in logfile.readlines():
                    self.actual_edited_pages.add(str(line).strip())
            print('successfully loaded the process state file from : %s' % (self.cache_file))

def init(config):
    total_count = config.get('article_count', 5)
    if config['state_file'] is None:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        config['state_file'] = os.path.join(dir_path, 'edited_pages.log')
    editWikiHandler = EditWikiPages(config['number_mapping'], config['exclude_regex'], config['state_file'],\
        config['edit_msg'], max_allowed_edits_per_page=config['max_edits_per_article'], debug=True, \
            highlight_edits=config['highlight_edits']) 
    for page in RandomPageGenerator(total=total_count, site=pywikibot.Site(), namespaces=0):
        editWikiHandler.editPage(page)        

    print(editWikiHandler.stats)

if __name__ == "__main__":
    config = {
        'article_count': 20, #total number of articles to be edited
        'max_edits_per_article': -1,  #set -1 for infinite proposed edits per page
        'number_mapping': {  #language specific change
            "0": "०",
            "1": "१",
            "2": "२",
            "3": "३",
            "4": "४",
            "5": "५",
            "6": "६",
            "7": "७",
            "8": "८",
            "9": "९"
        },
        #don't edit exclude_regex
        'exclude_regex': {
            "html_tags": "<\w+[\s|\w]*>(?>[^<>]+|(?R))*</\w+>",
            "reference_tags": "<ref .*>.*?</ref>",
            "wiki_links": "\[\[(?>[^\[\]]+|(?R))*\]\]",
            "curly_braces": "{{(?>[^{}]+|(?R))*}}",
            "url": "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            "www": "www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            "comments" : "<--.*?-->",
            "styles" : "\[\|.*?\|\]",
            "tables" : '{\|.*?\|}',
            "sections" : "\s(=+.*=+)\s",
            "references" : "\[(?>[^\[\]]|(?R))*\]",
        },
        'state_file': None,
        'edit_msg': "अंग्रेजी संख्या मूल्यों को हिंदी संख्या में परिवर्तित करना",
        #if True, it will highlight the edit in wikipage [NOTE:may not work properly on all terminal so turned off by default]
        'highlight_edits': False,
    }
    init(config)

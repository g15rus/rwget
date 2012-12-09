# coding: utf8
'''
Recursively wget, tornado asynchronous realisation
'''
import re
import argparse
import logging

from tornado import httpclient, ioloop
from functools import partial
from urlparse import urljoin

parser = argparse.ArgumentParser()
parser.add_argument("-u", "--url", type=str, required=True,
                    help="set url to fetch recursively")
parser.add_argument("-m", "--max_urls", type=int, default=1000,
                    help="set max urls to fetch")
args = parser.parse_args()

#беспокоили warning-и от httpclient-а, пришлось их отключить
logger = logging.getLogger()
logger.setLevel(logging.ERROR)

class Wget(object):
    urls_count = 0
    total_max_urls = 1000
    urls = []
    result = {}
    
    def __init__(self, max_urls):
        self.http_client = httpclient.AsyncHTTPClient()
        self.total_max_urls = max_urls
    
    def handle_request(self, response, level, result_urls):
        '''Обрабатываем тело'''
        if not response.error:
            page_url = response.effective_url
            urls = re.findall(r'(?:href|src)=[\'"]+([^\'" >]+)', response.body)
            result_urls['items'] = []
            for item in urls:
                if item.find('#') == 0 or item.find('mailto:') == 0 or item.find('javascript:') == 0:
                    continue
                    
                #слишком много url-ов не нужно обрабатывать, иначе это может плохо кончиться
                if self.urls_count >= self.total_max_urls: 
                    ioloop.IOLoop.instance().stop()
                    break            

                #Формируем URL из текущего и урла страницы
                current_url = urljoin(page_url, item)

                #если url уже был обработан, то он не нужен                
                if current_url in self.urls:
                    continue
                else:
                    self.urls.append(current_url)

                self.urls_count += 1

                #Добавляем новый URL в результирующий массив и отправляем его обрабатываться                 
                current_item = {}
                result_urls['items'].append(current_item)
                self.process_url(current_url, level = level + 1, result_urls = current_item)
        else:
            try:
                response.rethrow()
            except Exception, e:
                result_urls['error'] = "%s;%s" % (response.code, e)

        
    def handle_head(self, response, level, result_urls):
        '''Обрабатываем ответ HEAD запроса и если это html документ, то делаем запрос всего документа'''
        if response.error:
            try:
                response.rethrow()
            except Exception, e:
                result_urls['error'] = "%s;%s" % (response.code, e)
                return
        if response.code == 200 and 'Content-Type' in response.headers and 'html' in response.headers['Content-Type']:
            self.http_client.fetch(response.effective_url, 
                partial(self.handle_request, level = level, result_urls = result_urls), 
                method="GET", request_timeout=3
            )

                    
    def process_url(self, url, level = 0, result_urls = None):
        '''Для начала делаем HEAD запрос, чтобы понять нужно ли нам получать все тело'''
        result_urls = self.result if result_urls == None else result_urls
        result_urls['url'] = url
        self.http_client.fetch(url, 
            partial(self.handle_head, level = level, result_urls = result_urls), 
            method="HEAD", request_timeout=3
        )
        
    
wget_obj = Wget(args.max_urls)
ioloop.IOLoop.instance().add_callback(partial(wget_obj.process_url, args.url))
ioloop.IOLoop.instance().start()

#wget_obj.result содержит древовидную структуру URL-ов
#можно делать что угодно... решил просто вывести на экран
import pprint
pp = pprint.PrettyPrinter(indent=4)
pp.pprint(wget_obj.result)

"""
Code created in 2020.11.4 on MacOS, suitable for most current NYT webpage
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import re
import csv
import threading
import signal
import time
import atexit


class StopFetchingException(Exception):
    pass


class RestartException(Exception):
    pass


class SubscribeException(Exception):
    pass


class FetchNTYArticlesBase:
    def __init__(self, NTY_developer_key, start_year, start_month, month_number, filename, thread_lock,
                 previous_fetch=0,
                 driver_type=0):
        self.__init_parameters = [NTY_developer_key, start_year, start_month, month_number]
        self.__api_key = NTY_developer_key
        self.__response_details = []
        self.__filename = filename
        self.__driver_type = driver_type
        self.__thread_lock = thread_lock
        if previous_fetch == 0:
            with open(self.__filename, 'w') as csv_file:
                spam_writer = csv.writer(csv_file)
                spam_writer.writerow(
                    ['title', 'headline', 'text', 'authors', 'Keywords', 'pub_date', 'url', 'document_type',
                     'section_name',
                     'abstract', 'lead_paragraph', 'news_desk'])
        self.count = previous_fetch
        # using two browser driver
        if driver_type == 1:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_experimental_option("prefs", {'profile.managed_default_content_settings.javascript': 2})
            chrome_options.add_argument('--disable-dev-shm-usage')
            # chrome_options.add_argument('--headless')
            # uncomment following line in ubuntu
            # chrome_options.add_argument('--proxy-server=socks5://10.15.89.127:10809')
            chrome_options.add_argument('blink-settings=imagesEnabled=false')
            chrome_options.add_argument('--disable-gpu')
            self.browser = webdriver.Chrome(executable_path="./chromedriver", options=chrome_options)
        elif driver_type == 0:
            self.browser = webdriver.Safari()
        # set time our parameter
        self.browser.set_page_load_timeout(360)

    def run_test(self):
        self.fetch_month_meta(2020, 11)
        result_list = []
        for article in self.__response_details[self.count:]:
            tem = self.fetch_one_article(article)
            if tem:
                result_list.append(tem)

    def run(self):
        NTY_developer_key, start_year, start_month, month_number = self.__init_parameters
        month_iter = MonthIterator(start_year, start_month, month_number)
        try:
            for data in month_iter:
                self.fetch_month_meta(data[0], data[1])
                print("Total news: %d current process: %d" % (len(self.__response_details), self.count))
                result_list = []
                for article in self.__response_details[self.count:]:
                    self.count += 1
                    tem = self.fetch_one_article(article)
                    if tem:
                        result_list.append(tem)
                    print("Article Fetched: %d / %d month: %d" % (
                        self.count, len(self.__response_details), start_month))
                    """try:
                        tem = self.fetch_one_article(article)
                        if tem:
                            result_list.append(tem)
                        print("Article Fetched: %d / %d month: %d" % (
                            self.count, len(self.__response_details), start_month))
                        time.sleep(1)
                    except Exception as e:
                        print("Fetch Error, skipping...." + "\n" + str(e))
                        if type(e) == SubscribeException or type(e) == TimeoutError:
                            # subscribe window show up, restart browser to avoid
                            raise StopFetchingException"""
                    # write every five article
                    if len(result_list) > 5 or self.__response_details[-1] == article:
                        with open(self.__filename, 'a') as csv_file:
                            spam_writer = csv.writer(csv_file)
                            spam_writer.writerows(result_list)
                        result_list.clear()
        except StopFetchingException as e:
            print("Stop at Year: %d, Month: %d" % month_iter.get_current())
            raise RestartException
        self.quit_browser()

    def fetch_month_meta(self, year, month):
        try:
            with open("./local_data/{}_{}.json".format(year, month), "r") as f:
                json_raw = f.read()
        except Exception as e:
            print("local file not found")
            print(e)
            self.browser.get(
                'https://api.nytimes.com/svc/archive/v1/{}/{}.json?api-key={}'.format(year, month, self.__api_key))
            json_raw = self.browser.find_element_by_tag_name('pre').text
            print(json_raw)
            with open("./local_data/{}_{}.json".format(year, month), "w") as f:
                print('saving to local file')
                f.write(json_raw)
        json_data = json.loads(json_raw)

        try:
            self.__response_details = json_data["response"]["docs"]
        except KeyError as e:
            print(e)
            print(json_data)

    def fetch_one_article(self, article):
        web_url = article["web_url"]
        print("\nfetching: {}\n".format(web_url), end="")
        title = article["headline"]["main"]
        keywords = article["keywords"]
        abstract = article["abstract"]
        pub_data = article["pub_date"]
        document_type = article["document_type"]
        section_name = article["section_name"]
        lead_paragraph = article["lead_paragraph"]
        news_desk = article["news_desk"]
        headline = article["headline"]

        authors = []
        for per in article["byline"]['person']:
            authors.append("{} {} {}".format(per["firstname"], per["middlename"], per["lastname"]))

        if self.__thread_lock:
            self.__thread_lock.acquire()
            self.browser.get(web_url)
            self.__thread_lock.release()
        else:
            self.browser.get(web_url)
        print(re.findall("\\$2.00 every 4 weeks for one year", self.browser.page_source))
        if re.findall("\\$2.00 every 4 weeks for one year", self.browser.page_source):
            raise SubscribeException("Subscribe window show up, restart browser!")
        article_dom = self.browser.find_elements_by_name("articleBody")

        if article_dom:
            article_dom = article_dom[0]
        else:
            return None
            # raise KeyError("Article body not found")
        paragraphs = article_dom.find_elements_by_class_name("StoryBodyCompanionColumn")
        text_article = title + "\n"
        print("paragraphs number: {}".format(len(paragraphs)), end="  ")
        for p in paragraphs:
            print(len(p.text), end=" ")
            text_article += p.text
            # separate subtitle with new lines \n
            sub_div = p.find_elements_by_tag_name("div")
            if sub_div:
                sub_title = sub_div[0].find_elements_by_tag_name("h2")
                if sub_title:
                    print(len(sub_title), end="  ")
                    for t in sub_title:
                        text_article = re.sub(t.text, "\n{}\n".format(t.text), text_article)
        print("article length: {}".format(len(text_article)))
        print("Fetch success!")
        return [title, headline, text_article, authors, keywords, pub_data, web_url, document_type, section_name,
                abstract, lead_paragraph, news_desk]

    def quit_browser(self):
        self.browser.quit()

    def get_progress(self):
        print("current count: %d" % self.count)
        return self.count


class FetchNTYArticlesSingleThread(FetchNTYArticlesBase):
    def fetch_one_article(self, article):
        signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.alarm(3600)
        return FetchNTYArticlesBase.fetch_one_article(self, article)

    @staticmethod
    def _handle_timeout(signum, frame):
        print("time out!", signum, frame)
        raise TimeoutError


class MonthIterator:
    def __init__(self, start_year, start_month, max_month):
        self.__year = start_year
        self.__month = start_month
        self.__count = 0
        self.__max_month = max_month

    def __iter__(self):
        self.__cur_month = self.__month - 1
        self.__cur_year = self.__year
        return self

    def __next__(self):
        if self.__cur_month < 12:
            self.__cur_month += 1
        else:
            self.__cur_year += 1
            self.__cur_month = 1
        if self.__count >= self.__max_month:
            self.__count = 0
            raise StopIteration
        self.__count += 1
        return self.__cur_year, self.__cur_month

    def get_current(self):
        return self.__cur_year, self.__cur_month


class MultiThread(threading.Thread):
    def __init__(self, threadID, name, start_year, start_month, start_index, lock, key, driver_type=0):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.key = key
        self.start_year = start_year
        self.start_month = start_month
        self.start_index = start_index
        self.driver_type = driver_type
        self.error_count = 0
        self.thread_lock = lock
        self.__fetch = None

    def run(self):
        print("start thread: %d" % self.threadID)
        try:

            self.__fetch = FetchNTYArticlesBase(self.key, self.start_year,
                                                self.start_month, 1,
                                                       "./result/result_{}.csv".format(self.start_month),
                                                self.thread_lock,
                                                self.start_index,
                                                self.driver_type)
            self.__fetch.run()
        except Exception as e:
            if type(e) == RestartException:
                print("RestartException received!")
            else:
                print("error at thread level!")
                print(e)

            self.shut_down()
            self.start_index = self.__fetch.get_progress()
            self.run()

    def shut_down(self):
        try:
            self.__fetch.quit_browser()
        except Exception as e:
            print(e)

    def get_progress(self):
        return self.__fetch.get_progress()


class Entry:
    def __init__(self, key, year, month):
        self.key = key
        self.__restart_count = 0
        self.timeout = 10800
        self.progress_1 = 0
        self.progress_2 = 0
        self.progress_3 = 0
        self.thread1 = None
        self.thread2 = None
        self.thread3 = None
        self.fetch = None
        self.meta = None
        self.year = year
        self.month = month
        atexit.register(self.destructor)

    # def run(self):
    #     # move timeout wrapper here
    #     signal.signal(signal.SIGALRM, self._handle_timeout)
    #     signal.alarm(self.timeout)
    #     lock = threading.Lock()
    #     print("Thread init progresses: %d %d %d" % (self.progress_1, self.progress_2, self.progress_3))
    #     self.thread1 = MultiThread(1, "threading_1", 2020, 6, self.progress_1, lock, self.key, 0)
    #     self.thread2 = MultiThread(2, "threading_2", 2020, 8, self.progress_2, lock, self.key, 1)
    #     # self.thread3 = MultiThread(3, "threading_3", 2020, 7, self.progress_3, lock, 1)
    #
    #     self.thread1.start()
    #     # self.thread2.start()
    #     self.thread1.join()
    #     self.thread2.join()
    #     # self.thread3.start()

    def run_single(self):
        with open('local_data/process.json', 'r') as f:
            self.meta = json.loads(f.read())
            if '{}_{}'.format(self.year, self.month) in self.meta:
                self.progress_1 = self.meta['{}_{}'.format(self.year, self.month)]
                print('continue at {}'.format(self.progress_1))
            else:
                self.meta['{}_{}'.format(self.year, self.month)] = 0
                self.progress_1 = 0

        signal.signal(signal.SIGALRM, self._handle_single_timeout)
        signal.alarm(300)
        try:
            self.fetch = FetchNTYArticlesSingleThread(self.key, self.year, self.month, 1,
                                                      "./result/result_{}_{}.csv".format(self.year, self.month), None, self.progress_1, 1)
            self.fetch.run()
        except Exception as e:
            print(e)
            print("restarting browser!")
            time.sleep(5)
            self.save_current_process()
            try:
                self.progress_1 = self.fetch.get_progress() - 1
                self.fetch.quit_browser()
            except Exception as e:
                print("close browser error!")
                print(e)

            time.sleep(5)
            self.run_single()

    def run_test(self):
        self.fetch = FetchNTYArticlesSingleThread(self.key, self.year, self.month, 1,
                                                  "./result/test.csv".format(self.year, self.month), None,
                                                  0, 1)
        self.fetch.run_test()

    def destructor(self):
        print('saving current progress')
        if self.fetch:
            self.save_current_process()

    def save_current_process(self):
        with open('local_data/process.json', 'w') as f:
            self.meta['{}_{}'.format(self.year, self.month)] = self.fetch.get_progress() - 1
            f.write(json.dumps(self.meta))

    def _handle_single_timeout(self, signum, frame):
        print("Restart time out, restart restart!")
        self.save_current_process()
        try:
            self.progress_1 = self.fetch.get_progress() - 1
            self.fetch.quit_browser()
        except Exception as e:
            print("Again close browser error!")
            print(e)
            return
        time.sleep(5)
        self.run_single()

    # def _handle_timeout(self, signum, frame):
    #     print("Time out detected from entry level!")
    #     self.progress_1 = self.thread1.get_progress()
    #     self.progress_2 = self.thread2.get_progress()
    #     # self.progress_3 = self.thread3.get_progress()
    #     print("Thread updated progresses: %d %d" % (self.progress_1, self.progress_2))
    #     self.thread1.shut_down()
    #     print("thread 1 shut down")
    #     time.sleep(3)
    #     self.thread2.shut_down()
    #     print("thread 2 shut down")
    #     # time.sleep(3)
    #     # self.thread3.shut_down()
    #     print("thread 3 shut down")
    #     time.sleep(3)
    #     self.__restart_count += 1
    #     if self.__restart_count < 1000:
    #         print("restarting!")
    #         self.run()
    #     else:
    #         print("Maximum restart from entry level")


if __name__ == '__main__':
    entry = Entry("iX6VXE3DKksRYoYUZagwAaBHSWGikHRV", 2021, 3)
    entry.run_single()

#!/usr/bin/env python
# -*- coding: UTF-8 -*-
__author__="Scott Hendrickson, Josh Montague" 

import sys
import codecs
import datetime
import time
import os
import re

from api import *
from simple_n_grams.simple_n_grams import SimpleNGrams

reload(sys)
sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
sys.stdin = codecs.getreader('utf-8')(sys.stdin)

#############################################
# Some constants to configure column retrieval from TwacsCSV
DATE_INDEX = 1
TEXT_INDEX = 2
LINKS_INDEX = 3
USER_NAME_INDEX = 7 
OUTPUT_PAGE_WIDTH = 120 
BIG_COLUMN_WIDTH = 32

class QueryElements(Query):

    query_keys = [ "pt_filter"
                    , "max_results"
                    , "start"
                    , "end"
                    , "count_bucket"
                    , "query" ]
    last_query_params = None

    def get(self
            , pt_filter = None
            , max_results = 100
            , start = None
            , end = None
            , count_bucket = None
            , query = False):
        """Function the runs an API query only when parameters have changed.  This allows one
        to make multiple calls to analytics methods on a single query."""
        if self.last_query_params is None or not all(
                [locals()[k] == self.last_query_params[k] for k in self.query_keys]):
            # run the query
            self.last_query_params = {}
            for k in self.query_keys:
                self.last_query_params[k] = locals()[k] 
            self.query_api(**self.last_query_params)
            self.freq = None
            # else nothing new to do

    def get_activities(self, **kwargs):
        self.get(**kwargs)
        for x in self.get_activity_set():
            yield x

    def get_time_series(self, **kwargs):
        self.get(**kwargs)
        for x in self.time_series:
            yield x

    def get_top_links(self, n=20, **kwargs):
        self.get(**kwargs)
        self.freq = SimpleNGrams(char_upper_cutoff=100, tokenizer="space")
        for x in self.get_list_set():
            link_str = x[LINKS_INDEX]
            if link_str != "GNIPEMPTYFIELD" and link_str != "None":
                exec("link_list=%s"%link_str)
                for l in link_list:
                    self.freq.add(l)
            else:
                self.freq.add("NoLinks")
        return self.freq.get_tokens(n)

    def get_top_users(self, n=50, **kwargs):
        self.get(**kwargs)
        self.freq = SimpleNGrams(char_upper_cutoff=20, tokenizer="twitter")
        for x in self.get_list_set():
            self.freq.add(x[USER_NAME_INDEX])
        return self.freq.get_tokens(n) 

    def get_top_grams(self, n=20, **kwargs):
        self.get(**kwargs)
        self.freq = SimpleNGrams(char_upper_cutoff=20, tokenizer="twitter")
        for x in self.get_list_set():
            self.freq.add(x[TEXT_INDEX])
        return self.freq.get_tokens(n) 
            
    def get_geo(self, **kwargs):
        self.get(**kwargs)
        for rec in self.get_activity_set():
            lat, lng = None, None
            if "geo" in rec:
                if "coordinates" in rec["geo"]:
                    [lat,lng] = rec["geo"]["coordinates"]
                    activity = { "id": rec["id"].split(":")[2]
                        , "postedTime": rec["postedTime"].strip(".000Z")
                        , "latitude": lat
                        , "longitude": lng }
                    yield activity
 
    def get_frequency_items(self, size = 20):
        """Retrieve the token list structure from the last query"""
        if self.freq is None:
            raise VallueError("No frequency available for use case")
        return self.freq.get_tokens(size)

    def __repr__(self):
        if self.last_query_params["count_bucket"] is None:
            res = [u"-"*OUTPUT_PAGE_WIDTH]
            rate = self.get_rate()
            unit = "Tweets/Minute"
            if rate < 0.01:
                rate *= 60.
                unit = "Tweets/Hour"
            res.append("     PowerTrack Rule: \"%s\""%self.last_query_params["pt_filter"])
            res.append("  Oldest Tweet (UTC): %s"%str(self.oldest_t))
            res.append("  Newest Tweet (UTC): %s"%str(self.newest_t))
            res.append("           Now (UTC): %s"%str(datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
            res.append("        %5d Tweets: %6.3f %s"%(self.res_cnt, rate, unit))
            res.append("-"*OUTPUT_PAGE_WIDTH)
            #
            self.get_top_users(**self.last_query_params)
            fmt_str = u"%{}s -- %10s     %8s (%d)".format(BIG_COLUMN_WIDTH)
            res.append(fmt_str%( "users", "tweets", "activities", self.res_cnt))
            res.append("-"*OUTPUT_PAGE_WIDTH)
            fmt_str =  u"%{}s -- %4d  %5.2f%% %4d  %5.2f%%".format(BIG_COLUMN_WIDTH)
            for x in self.freq.get_tokens(20):
                res.append(fmt_str%(x[4], x[0], x[1]*100., x[2], x[3]*100.))
            res.append("-"*OUTPUT_PAGE_WIDTH)
            #
            self.get_top_links(**self.last_query_params)
            fmt_str = u"%{}s -- %10s     %8s (%d)".format(int(2.5*BIG_COLUMN_WIDTH))
            res.append(fmt_str%( "links", "mentions", "activities", self.res_cnt))
            res.append("-"*OUTPUT_PAGE_WIDTH)
            fmt_str =  u"%{}s -- %4d  %5.2f%% %4d  %5.2f%%".format(int(2.5*BIG_COLUMN_WIDTH))
            for x in self.freq.get_tokens(20):
                res.append(fmt_str%(x[4], x[0], x[1]*100., x[2], x[3]*100.))
            res.append("-"*OUTPUT_PAGE_WIDTH)
            #
            self.get_top_grams(**self.last_query_params)
            fmt_str = u"%{}s -- %10s     %8s (%d)".format(BIG_COLUMN_WIDTH)
            res.append(fmt_str%( "terms", "mentions", "activities", self.res_cnt))
            res.append("-"*OUTPUT_PAGE_WIDTH)
            fmt_str =u"%{}s -- %4d  %5.2f%% %4d  %6.2f%%".format(BIG_COLUMN_WIDTH)
            for x in self.freq.get_tokens(20):
                res.append(fmt_str%(x[4], x[0], x[1]*100., x[2], x[3]*100.))
            res.append("-"*OUTPUT_PAGE_WIDTH)
        else:
            res = ["{:%Y-%m-%dT%H:%M:%S},{}".format(x[2], x[1])
                        for x in self.time_series]
        return u"\n".join(res)

if __name__ == "__main__":
    g = QueryElements("shendrickson@gnip.com"
            , "XXXXXPASSWORDXXXXX"
            , "https://search.gnip.com/accounts/shendrickson/search/wayback.json")
    list(g.get_time_series(pt_filter="bieber", count_bucket="hour"))
    print unicode(g)
    print list(g.get_activities(pt_filter="bieber", max_results = 10))
    print list(g.get_geo(pt_filter = "bieber has:geo", max_results = 10))
    print list(g.get_time_series(pt_filter="beiber", count_bucket="hour"))
    print list(g.get_top_links(pt_filter="beiber", max_results=100, n=30))
    print list(g.get_top_users(pt_filter="beiber", max_results=100, n=30))
    print list(g.get_top_grams(pt_filter="bieber", max_results=100, n=50))
    print list(g.get_frequency_items(10))
    print unicode(g)
    print g.get_rate()
    g.query_api(pt_filter="bieber", query=True)
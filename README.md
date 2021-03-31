# WebCrawlerForNTYTimes

## How does program work?

### Find article urls by 'https://api.nytimes.com/svc/archive/v1/{}/{}.json?api-key={}'.format(year, month, self.__api_key))

## How to run?
### python main.py

## Tips:

### Single thread works well and multi-thread will stack after some time
### Output files will be placed under ./result
### Parameters (self.progressx) in Entry Class is required to be modified to mark the start index of remaining articles.

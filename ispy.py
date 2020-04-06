import time
import os
import re
import requests
import yaml

import numpy as np
import PIL.Image
import plyvel
import praw
import prawcore
import tensorflow as tf


db = plyvel.DB('/tmp/ispydb/', create_if_missing=True)
model = tf.keras.models.load_model('model.h5')
# you need to have config.yaml
with open('config.yaml', 'r') as f:
  config = yaml.load(f, Loader=yaml.FullLoader)['reddit']
reddit = praw.Reddit(client_id=config['client_id'], client_secret=config['client_secret'],
                     password=config['password'], user_agent='ispy',
                     username=config['username'])


def predict(path):
  """predict whether an image is a screenshot or not"""
  global model

  # preprocess image
  try:
    img = PIL.Image.open(path).resize((224, 224)).convert('RGB')
  except OSError:
    return None, None
  img = np.asarray(img) / 255.
  img = img.reshape((1, 224, 224, 3)) # set batch size to 1

  # [0][0] selects the first (only) node from the first (only) item in this batch.
  score = model.predict(img)[0][0]
  return int(score*100), bool(score > .65)


def get_image_url(post_url):
  """get the url of the image from a content url"""
  if "i.redd.it" in post_url or \
      "i.imgur.com" in post_url or \
      post_url.endswith(".jpg") or \
      post_url.endswith(".png"):
    return post_url

  if "imgur.com" in post_url:
    imgur_html = requests.get(post_url).text
    links = re.findall(r'https:\/\/i\.imgur\.com\/\w+\.(?:jpg|png)', imgur_html)
    return links[0]

  return None


def is_checked(post_id):
  global db
  return db.get(post_id.encode('utf-8')) is not None


def download(post):
  """download the image contained in a reddit post"""
  url = get_image_url(post.url)
  if not url:
    return None

  r = requests.get(url)
  if r.status_code == 200:
    ext = url.split('.')[-1]
    filename = post.id + ext
    with open(filename, 'wb') as f:
      f.write(r.content)
  else:
    return None

  return filename


def add_comment(post, score):
  """blame the user"""
  text = '''
u/{user}, thank you for your submission. This post has been automatically removed because it appears to violate Rule 1 ({confidence}% confidence).

* Rule 1A: No screenshots or pics where the only focus is a screen.

* Rule 1B: No pictures with added or superimposed digital text, emojis, and "MS Paint"-like scribbles. Exceptions to this rule include watermarks serving to credit the original author, and blurring/boxing out of personal information. "Photoshopped" or otherwise manipulated images are allowed.

In rare cases, exceptions are made for the purpose of censoring personal information or crediting the photographer. If you feel that this is such an exception, or that the bot has made a mistake, [send us a modmail message](https://reddit.com/message/compose?to=%2Fr%2Fpics) and we will consider re-approving your post. Please upvote or downvote this comment depending on whether the prediction is correct so future generations will be smarter. Thank you.

---

I am a bot, and this action was performed automatically. Visit the [GitHub](https://github.com/rickwierenga/ispyscreenshots) for more information.
  '''
  post.reply(text.format(**{
    'user': post.author,
    'confidence': score}))


def main():
  while True:
    # we expect at most 10 new posts in 10 seconds
    new_posts = reddit.subreddit('pics').new(limit=10)
    while True:
      try:
        post = next(new_posts)
        print(post.id)
      except StopIteration:
        break
      except prawcore.exceptions.ServerError:
        break

      if is_checked(post.id):
        continue

      path = download(post)
      if not path:
        continue
      score, not_allowed = predict(path)
      if score is None or not_allowed is None:
        continue
      if not_allowed:
        add_comment(post, score)

      os.remove(path)
      # if everything went ok, don't check this post again.
      db.put(post.id.encode('utf-8'), bytes([score]))

    time.sleep(10)


if __name__ == '__main__':
  main()

#!/usr/bin/env python3
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
import pytesseract
import tensorflow as tf


db = plyvel.DB('/tmp/ispydb/', create_if_missing=True)
dirname = os.path.dirname(__file__)
model_filename = os.path.join(dirname, 'model.h5')
model = tf.keras.models.load_model(model_filename)
# you need to have config.yaml
config_filename = os.path.join(dirname, 'config.yaml')
with open(config_filename, 'r') as f:
  config = yaml.load(f, Loader=yaml.FullLoader)['reddit']
reddit = praw.Reddit(client_id=config['client_id'], client_secret=config['client_secret'],
                     password=config['password'], user_agent='ispy',
                     username=config['username'])


def predict(path):
  """predict whether an image is a screenshot or not"""
  global model

  # load image
  try:
    img = PIL.Image.open(path).convert('RGB')
  except OSError:
    return None, None

  # see if we can read text
  try:
    contains_text = (pytesseract.image_to_string(img) != '')
  except (pytesseract.pytesseract.TesseractError, OSError):
    return None, None

  # preprocess image for ML
  img = img.resize((224, 224))
  img = np.asarray(img) / 255.
  img = img.reshape((1, 224, 224, 3)) # set batch size to 1

  # [0][0] selects the first (only) node from the first (only) item in this batch.
  score = model.predict(img)[0][0]

  # post should be removed if we have 65%+ confidence and text
  return int(score*100), bool(score > .65) and contains_text


def get_image_url(post_url):
  """get the url of the image from a content url"""
  if "i.redd.it" in post_url or \
      "i.imgur.com" in post_url or \
      post_url.endswith(".jpg") or \
      post_url.endswith(".png"):
    return post_url

  if "imgur.com" in post_url:
    imgur_html = requests.get(post_url).text
    try:
      return re.findall(r'https:\/\/i\.imgur\.com\/\w+\.(?:jpg|png)', imgur_html)[0]
    except IndexError:
      # no matches were found.
      return None

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
  link = (
    'https://www.reddit.com/message/compose?to=/r/pics&subject=Screenshot%20Removal%20Appeal&message='
    '**DO%20NOT%20MODIFY**%0D%0ALink%20to%20post:%20{url}%0D%0A---%0D%0A%0D%0AAdditional%20Details:'
  ).format(**{'url': "https://www.reddit.com" + post.permalink})

  """blame the user"""
  text = '''
u/{user}, thank you for your submission. This post has been automatically removed because it appears to violate Rules 1/2 ({confidence}% confidence).

* Rule 1: No screenshots or pics where the only focus is a screen.

* Rule 2: No pictures with added or superimposed digital text, emojis, and "MS Paint"-like scribbles. Exceptions to this rule include watermarks serving to credit the original author, and blurring/boxing out of personal information. "Photoshopped" or otherwise manipulated images are allowed.
  '''

  post.reply(text.format(**{
    'user': post.author,
    'confidence': score,
    'link': link}))


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

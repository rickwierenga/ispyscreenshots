# ISpyScreenshots V2

A Reddit bot that helps enforce rule #1 of [r/pics](https://old.reddit.com/r/pics/).

Rule #1:

> (1A) No screenshots or pics where the only focus is a screen.
>
> (1B) No pictures with added or superimposed digital text, emojis, and "MS Paint"-like scribbles. Exceptions to this rule include watermarks serving to credit the original author, and blurring/boxing out of personal information. "Photoshopped" or otherwise manipulated images are allowed.

In rare cases, exceptions are made for the purpose of censoring personal information or crediting the photographer. If you feel that this is such an exception, or that the bot has made a mistake, [send a modmail](https://www.reddit.com/message/compose?to=%23pics) message and we will consider re-approving your post.

## How it works

This bot uses machine learning to predict whether an image violates rule #1. The model was trained with [TensorFlow](https://www.tensorflow.org), see [`train.ipynb`](train.ipynb). For machine learning people, the model is just a [169 layer DenseNet](https://arxiv.org/pdf/1608.06993.pdf) trained from scratch. The image is also run through an OCR program to determine whether or not text is present, because images without text can't violate rule #1. This helps protect against a bias for digital art. If the model's confidence is more than 65% and text is present, the post will be removed.

It loads the newest posts from r/pics every 10 seconds and checks which posts are not classified yet. New posts are temporarily downloaded, preprocessed and classified.

Why use ML instead of simply measuring "flatness" (variance)?

* Pictures of screens are also not allowed.

* Does not respect rule 1B.

* Some pictures have artificial borders.

* Many pictures are taken with high quality cameras so they don't have a lot of noise in them.

---

&copy;2020 Rick Wierenga

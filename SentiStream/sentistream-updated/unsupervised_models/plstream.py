# pylint: disable=import-error
# pylint: disable=no-name-in-module
import multiprocessing

from sklearn.metrics import accuracy_score


from unsupervised_models.utils import cos_similarity
from utils import tokenize, clean_for_wv, train_word_vector_algo, get_average_word_embeddings


class PLStream():
    """
    Online sentiment analysis using PLStream framework.

    Attributes:
        neg_coef (float): Negative coefficient for temporal trend.
        pos_coef (float): Positive coefficient for temporal trend.
        neg_count (int): Number of negative samples seen so far.
        pos_count (int): Number of positive samples seen so far.
        update (bool): Flag determining whether to update word vector model or train from scratch.
        batch_size (int): Number of samples to wait on before processing.
        temporal_trend_detection (bool): If True, perform temporal trend detection.
        confidence (float): Confidence difference to distinguish polarity.
        acc_list(list): Store accuracy of each batch.
        wv_model (class): The word vector model.
        pos_ref (list): List of positive reference words.
        neg_ref (list): List of negative reference words.
        labels (list): Labels of data
        texts (list): Texts/Reviews of data
    """

    def __init__(self, word_vector_algo, vector_size=20, batch_size=250,
                 temporal_trend_detection=True, confidence=0.5):
        """
        Initialize PLStream with hyperparameters.

        Args:
            word_vector_algo (class): Type of word vector algorithm to use (either 'Word2Vec' or
                                    'FastText').
            vector_size (int, optional): Size of word vectors. Defaults to 20.
            batch_size (int): Number of samples to wait on before processing. Defaults to 250.
            temporal_trend_detection (bool): If True, perform temporal trend detection.
                                            Defaults to True.
            confidence (float): Confidence difference to distinguish polarity. Defaults to 0.5.
        """
        self.neg_coef = 0.5
        self.pos_coef = 0.5
        self.neg_count = 0
        self.pos_count = 0  # watch-out for integer overflow error in horizon.

        self.update = False
        self.batch_size = batch_size
        self.temporal_trend_detection = temporal_trend_detection
        self.confidence = confidence

        self.acc_list = []

        # Initialize word vector model.
        num_workers = int(0.8 * multiprocessing.cpu_count())
        self.wv_model = word_vector_algo(
            vector_size=vector_size, workers=num_workers)

        # Set up positive and negative reference words for trend detection.
        self.pos_ref = ['love', 'best', 'beautiful', 'great',
                        'cool', 'awesome', 'wonderful', 'brilliant', 'excellent', 'fantastic']
        self.neg_ref = ['bad', 'worst', 'stupid', 'disappointing',
                        'terrible', 'rubbish', 'boring', 'awful', 'unwatchable', 'awkward']

        self.labels = []
        self.texts = []

    def process_data(self, data):
        """
        Process incoming stream and output polarity of stream data.

        Args:
            data (tuple): Contains label and text data.

        Returns:
            tuple or str: 'BATCHING' if collecting data for batch, else, accuracy and f1 score 
                        for current batch's predictions.
        """

        label, text = data

        # Append label and preprocessed text to respective lists.
        self.labels.append(label)
        # batchwise will improve performance --- but only if this creates overhead in stream---
        self.texts.append(clean_for_wv(tokenize(text)))

        # Train model & classify once batch size is reached.
        if len(self.labels) >= self.batch_size:
            train_word_vector_algo(
                self.wv_model, self.texts, 'plstream-wv.model', update=self.update)

            # Get predictions and confidence scores.
            conf, preds = self.eval_model(self.texts, self.labels)

            # Generate output data
            output = [[c, p, t] for c, p, t in zip(conf, preds, self.texts)]

            # Clear the lists for the next batch
            self.update = True
            self.labels = []
            self.texts = []

            return output
        return 'BATCHING'

    def update_temporal_trend(self, y_preds):
        """
        Update temporal trend of sentiment analysis based on predictions.

        Args:
            y_preds (list): Predicted sentiments for current batch.
        """
        # Calculate positive and negative predictions so far.
        for pred in y_preds:
            if pred == 1:
                self.pos_count += 1
            else:
                self.neg_count += 1

        # Update temporal trend based on predictions.
        total = self.neg_count + self.pos_count
        self.neg_coef = self.neg_count / total
        self.pos_coef = self.pos_count / total

    def eval_model(self, sent_tokens, labels):
        """
        Evaluate model on current batch

        Args:
            sent_tokens (list): Tokenized texts.
            labels (list): Sentiment labels.

        Returns:
            tuple: Accuracy and F1 score of model on current batch.
        """
        confidence, y_preds = [], []
        for tokens in sent_tokens:
            conf, y_pred = self.predict(tokens)
            confidence.append(conf)
            y_preds.append(y_pred)

        self.update_temporal_trend(y_preds)

        self.acc_list.append(accuracy_score(labels, y_preds))
        return confidence, y_preds

    def predict(self, tokens):
        """
        Predict polarity of text based using PLStream.

        Args:
            tokens (list): Tokenized words in a text.

        Returns:
            tuple: Confidence of predicted label and predicted label.
        """
        # Calculate average word embeddings for text.
        vector = get_average_word_embeddings(self.wv_model, tokens)

        # Calculate cosine similarity between sentence and reference words.
        cos_sim_pos = sum(cos_similarity(
            vector, self.wv_model.wv[word])
            for word in self.pos_ref if word in self.wv_model.wv.key_to_index)
        cos_sim_neg = sum(cos_similarity(
            vector, self.wv_model.wv[word])
            for word in self.neg_ref if word in self.wv_model.wv.key_to_index)

        # Predict polarity based on temporal trend and cosine similarity.
        if cos_sim_neg - cos_sim_pos > self.confidence:
            return cos_sim_neg - cos_sim_pos, 0
        if cos_sim_pos - cos_sim_neg > self.confidence:
            return cos_sim_pos - cos_sim_neg, 1
        if self.temporal_trend_detection:
            if cos_sim_neg * self.neg_coef >= cos_sim_pos * self.pos_coef:
                return cos_sim_neg - cos_sim_pos, 0
            return cos_sim_pos - cos_sim_neg, 1
        if cos_sim_neg > cos_sim_pos:
            return cos_sim_neg - cos_sim_pos, 0
        return cos_sim_pos - cos_sim_neg, 1

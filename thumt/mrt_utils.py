import math
import numpy

def getMRTBatch(x, xmask, y, ymask, config, model, data):
	'''
		Get a batch for MRT training 

		:type x: numpy array
		:param x: the indexed source sentence

		:type xmask: numpy array
		:param xmask: indicate the length of each sequence in source sequence

		:type y: numpy array
		:param y: the indexed target sentence

		:type ymask: numpy array
		:param ymask: indicate the length of each sequence in target sequence

		:type config: dict
		:param config: the configuration

		:type model: Model
		:param model: the NMT model

		:type data: DataCollection
		:param data: the data manager
	'''
	# random sampling
	sampleN = config['sampleN']
	myL = int(config['LenRatio'] * len(y))
	samples, probs = model.sample(x.squeeze(), myL, sampleN)
	samples = samples.transpose()

	# remove repeated sentences and calculate BLEU score
	y, b = getUnique(samples, y, config, model, data)
	b = numpy.array(b, dtype = 'float32')
	Y, YM = getYM(y, config)
	diffN = len(b)

	X = numpy.zeros((x.shape[0], diffN), dtype = 'int64')
	x = x + X
	X = numpy.zeros((x.shape[0], diffN), dtype = 'float32')
	xmask = xmask + X
	y = Y
	ymask = YM
	MRTLoss = b

	return x, xmask, y, ymask, MRTLoss


def getUnique(samples, y, config, model, data):
	'''
		Remove repeated sentences from sampling results.
		Then calculate BLEU score for each sentence.

		:type y: numpy array
		:param y: the indexed target sentence

		:type config: dict
		:param config: the configuration

		:type model: Model
		:param model: the NMT model

		:type data: DataCollection
		:param data: the data manager
	'''
	# add the reference to the samples
	dic = {}
	ty = y.squeeze().tolist()
	sen = cutSen(ty,config)
	if len(sen) == 1:
		return [[str(config['index_eos_trg'])]], [1.0]
	words = [str(i) for i in sen]
	sen = sen[: -1]
	ref,lens = getRefDict(words[: -1], 4)
	dic[' '.join(words)] = 1.0

	# calculate BLEU score for each sample
	n=len(samples[0])
	for i in range(n):
		sen = samples[:, i]
		sen = cutSen(sen.tolist(), config)
		if len(sen) == 1:
			dic[str(config['index_eos_trg'])] = 0.0
			continue
		words = [str(i) for i in sen]
		sen = sen[: -1]
		tmp = ' '.join(words)
		if tmp in dic:
			continue
		else:
			dic[tmp] = calBleu(words[: -1], ref, lens, 4)
	l = []
	b = []
	for sen in dic:
		words = sen.split(' ')
		l.append(words)
		b.append(dic[sen])
	return l, b


def getYM(y, config):
	'''
		Get masks which indicate the length of target sentences

		:type y: list
		:param y: the indexed sentences

		:type config: dict
		:param config: the configuration
	'''
	n = len(y)
	max = 0 
	for i in range(n):
		tmp = len(y[i])
		if max < tmp:
			max = tmp
	Y = numpy.ones((max, n), dtype = 'int64') * config['index_eos_trg']
	Ymask = numpy.zeros((max, n), dtype = 'float32')
	for i in range(n):
		si = y[i]
		ly = len(si)
		Y[0 : ly, i] = y[i]
		Ymask[0 : ly, i] = 1
	return Y, Ymask

def my_log(a):
	if a == 0:
		return -1000000
	return math.log(a)

def cutSen(x, config):
	'''
		Cut the part after the end-of-sentence symbol

		:type x: list
		:param x: indexed sentence

		:type config: dict
		:param config: the configuration
	'''
	if config['index_eos_trg'] not in x:
		return x
	else:
		return x[:x.index(config['index_eos_trg'])+1]


def getRefDict(words, ngram):
	'''
		Get the count of n-grams in the reference

		:type words: list
		:param words: indexed sentence

		:type ngram: int
		:param ngram: maximum length of counted n-grams
	'''
	lens = len(words)
	now_ref_dict = {}
	for n in range(1, ngram + 1):
		for start in range(lens - n + 1):
			gram = ' '.join([str(p) for p in words[start : start + n]])
			if gram not in now_ref_dict:
				now_ref_dict[gram] = 1
			else:
				now_ref_dict[gram] += 1
	return now_ref_dict, lens


def calBleu(x, ref_dict, lens, ngram):
	'''
		Calculate BLEU score with single reference

		:type x: list
		:param x: the indexed hypothesis sentence

		:type ref_dict: dict
		:param ref_dict: the n-gram count generated by getRefDict()

		:type lens: int
		:param lens: the length of the reference

		:type ngram: int
		:param ngram: maximum length of counted n-grams
	'''
	length_trans = len(x)
	words = x
	closet_length = lens
	sent_dict = {}
	for n in range(1, ngram + 1):
		for start in range(length_trans - n + 1):
			gram = ' '.join([str(p) for p in words[start : start + n]])
			if gram not in sent_dict:
				sent_dict[gram] = 1
			else:
				sent_dict[gram] += 1
	correct_gram = [0] * ngram
	for gram in sent_dict:
		if gram in ref_dict:
			n = len(gram.split(' '))
			correct_gram[n - 1] += min(ref_dict[gram], sent_dict[gram])
	bleu = [0.] * ngram
	smooth = 0
	for j in range(ngram):
		if correct_gram[j] == 0:
			smooth = 1
	for j in range(ngram):
		if length_trans > j:
			bleu[j] = 1. * (correct_gram[j] + smooth) / (length_trans - j + smooth)
		else:
			bleu[j] = 1
	brev_penalty = 1
	if length_trans < closet_length:
		brev_penalty = math.exp(1 - closet_length * 1. / length_trans)
	logsum = 0
	for j in range(ngram):
		logsum += my_log(bleu[j])
	now_bleu = brev_penalty * math.exp(logsum / ngram)
	return now_bleu

#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import sys
import copy
import time
import numpy
from numpy import array, zeros, ones, mean, average, tile, nonzero, \
    newaxis, isnan, isfinite

"""
Boundary precision and recall (BPR) evaluation for morphological
segmentation of words

Version: 1.0
Last modified: 2012-01-05

----------------------------------------------------------------------

Copyright (C) 2011-2012 Sami Virpioja <sami.virpioja@aalto.fi>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

----------------------------------------------------------------------

The users of this program are requested to refer to the following
article in their scientific publications:

  Sami Virpioja, Ville T. Turunen, Sebastian Spiegler, Oskar Kohonen,
  and Mikko Kurimo. Empirical comparison of evaluation methods for
  unsupervised learning of morphology. Traitement Automatique des
  Langues, 52(2), 2011.

The program calculates the precision and recall for a predicted morph
boundaries when compared to reference boundaries based on a gold
standard segmentation.

To allow analysis of ambiguous words, the segmentations may contain
alternative analyses. By default, the best matching alternatives are
found and applied. With --strictalts, one-to-one mapping between the
alternatives is selected using the Hungarian (Munkres) algorithm to
maximize the average F-score. This requires the Munkres module by
Brian M. Clapper. See

* http://pypi.python.org/pypi/munkres/ or
* http://software.clapper.org/munkres/

Input files should in a format similar to Morpho Challenge results:
The word and its analyses are separated by a tabular character, any
alternative analyses by a comma and a space, and the morphs of the
analyses by single space. Example:

evening	even ing, evening

The effect of each word to the overall precision and recall can be
modified by giving numerical weights (--weightFile). The file should
have word and its weight, separated by whitespace, per line.
"""

class Segmentation:
    """Stores the segmentations of words"""

    def __init__(self):
        self.data = {}
        self.wlist = []

    def get_data(self):
        """Return the stored segmentations (boundary vectors)"""
        return self.data

    def get_words(self):
        """Return the list of words"""
        return self.wlist

    def get_size(self):
        """Return the number of words"""
        return len(self.wlist)

    def get_segmentation(self, w):
        """Return the segmentation for given word"""
        return self.data[w]

    def string2bvect(self, mstr):
        """Convert segmentation to boundary vector"""
        v = []
        i = 1
        while i < len(mstr):
            l = mstr[i]
            if l == ' ':
                v.append(1)
                i += 1
            else:
                v.append(0)
            i += 1
        return numpy.array(v)

    def load(self, filename, wdict=None):
        """Load segmentations from given file

        Given a dictionary object wdict, load only the words found in it."""
        fobj = open(filename, 'r')
        for line in fobj:
            if line[0] == '#':
                continue
            line = line.rstrip()
            w, a = line.split("\t")
            if wdict == None or w in wdict:
                self.wlist.append(w)
                self.data[w] = []
                for mstr in a.split(", "):
                    b = self.string2bvect(mstr)
                    self.data[w].append(b)

    def equalize(self, ref):
        """Remove words that are not in the given segmentation instance"""
        for w in self.wlist:
            if not w in ref.data:
                del self.data[w]
        self.wlist = copy.copy(ref.wlist)

def recall_eval_single(pre, ref):
    """Calculate recall for boundary vectors"""
    tot = ref.sum()
    if tot == 0:
        return 1.0, 0
    diff = ref - pre
    E = (abs(diff) + diff) / 2 # recall errors
    r = float(tot - E.sum()) / tot
    return r, tot

def recall_eval(predicted, reference, weights=None):
    """Calculate recall for the segmentations of words"""
    wlist = reference.get_words()
    total = 0
    s = 0.0
    for i in range(len(wlist)):
        w = wlist[i]
        if len(w) < 2:
            continue
        refA = reference.get_segmentation(w)
        preA = predicted.get_segmentation(w)
        maxr = 0
        for ref in refA:
            tot = ref.sum()
            if tot == 0:
                maxr = 1.0
                continue
            for pre in preA:
                r, tmp = recall_eval_single(pre, ref)
                if r > maxr:
                    maxr = r
        if weights == None:
            total += 1
            s += maxr
        else:
            total += weights[i]
            s += weights[i] * maxr
    if total > 0:
        return s / total, total
    else:
        return 1.0, 0

def strict_eval(predicted, reference, weights=None):
    """Calculate recall for the segmentations of words using strict
    macthing of alternatives"""
    import munkres
    wlist = reference.get_words()
    rec_total = 0
    pre_total = 0
    rec_sum = 0.0
    pre_sum = 0.0
    for i in range(len(wlist)):
        w = wlist[i]
        if len(w) < 2:
            continue
        refA = reference.get_segmentation(w)
        preA = predicted.get_segmentation(w)
        
        ref_altnum = len(refA)
        pre_altnum = len(preA)
        n = max(ref_altnum, pre_altnum)
        w = [[0 for v in range(n)] for u in range(n)]
        results = {}
        
        for i in range(n):
            for j in range(n):
                if i < ref_altnum and j < pre_altnum:
                    rec_r, rec_t = recall_eval_single(preA[j], refA[i])
                    pre_r, pre_t = recall_eval_single(refA[i], preA[j])
                else:
                    pre_r = 0.0
                    rec_r = 0.0
                results[(i,j)] = (pre_r, rec_r)
                if pre_r + rec_r == 0:
                    f = 0.0
                else:
                    f = 2.0*pre_r*rec_r/(pre_r+rec_r)
                w[i][j] = 1.0 - f # cost

        m = munkres.Munkres()
        indexes = m.compute(w)

        pre_t = 0.0
        rec_t = 0.0
        for i, j in indexes:
            pre_t += results[(i,j)][0]
            rec_t += results[(i,j)][1]
        pre_t = pre_t / len(preA)
        rec_t = rec_t / len(refA)

        if weights == None:
            pre_sum += pre_t
            pre_total += 1
            rec_sum += rec_t
            rec_total += 1
        else:
            pre_sum += weights[i] * pre_t
            pre_total += weights[i]
            rec_sum += weights[i] * rec_t
            rec_total += weights[i]

    if pre_total == 0:
        pre_r = 1.0
    else:
        pre_r = pre_sum / pre_total
    if rec_total == 0:
        rec_r = 1.0
    else:
        rec_r = rec_sum / rec_total
    return pre_r, rec_r, pre_total, rec_total


if __name__ == "__main__":
    from optparse import OptionParser
    usage = """Usage: %prog -g goldFile -p predFile [options]"""

    parser = OptionParser(usage=usage)
    parser.add_option("-g", "--goldFile", dest="goldFile",
                      default = None,
                      help="gold standard segmentation file")
    parser.add_option("-p", "--predFile", dest="predFile",
                      default = None,
                      help="predicted segmentation file")
    parser.add_option("-s", "--strictalts", dest="strictalts",
                      default = False, action = "store_true",
                      help="strict matching of alternative analyses")
    parser.add_option("-w", "--weightFile", dest="weightFile",
                      default = None,
                      help="read word weights from file")
    (options, args) = parser.parse_args()

    if options.goldFile == None or options.predFile == None:
        parser.print_help()
        sys.exit()

    ts = time.time()

    if options.weightFile != None:
        wdict = {}
        fobj = open(options.weightFile, 'r')
        for line in fobj:
            word, weight = line.split()
            wdict[word] = float(weight)
        fobj.close()
    else:
        wdict = None

    goldstd = Segmentation()
    goldstd.load(options.goldFile, wdict)
    predicted = Segmentation()
    predicted.load(options.predFile, goldstd.get_data())
    goldstd.equalize(predicted)

    if wdict != None:
        wlist = goldstd.get_words()
        weights = zeros((len(wlist), 1))
        for i in range(len(wlist)):
            word = wlist[i]
            weights[i] = wdict[word]
    else:
        weights = None

    print "# Gold standard file: %s" % options.goldFile
    print "# Predictions file  : %s" % options.predFile
    print "# Evaluation options:"
    if options.weightFile != None:
        print "# - word weights loaded from %s" % options.weightFile
    if options.strictalts:
        print "# - strict matching of alternative analyses (--strictalts)"
        pre, rec, pren, recn = strict_eval(predicted, goldstd, weights)
    else:
        print "# - best local matching of alternative analyses"
        rec, recn = recall_eval(predicted, goldstd, weights=weights)
        pre, pren = recall_eval(goldstd, predicted, weights=weights)
    print "# Recall based on %s words" % recn
    print "# Precision based on %s words" % pren

    te = time.time()
    print "# Evaluation time: %.2fs" % (te-ts)
    print

    f = 2.0/(1.0/pre+1.0/rec)
    print "precision: %s" % pre
    print "recall   : %s" % rec
    print "fmeasure : %s" % f

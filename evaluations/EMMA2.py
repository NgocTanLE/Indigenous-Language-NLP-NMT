#!/usr/bin/python
from optparse import OptionParser
import re
import os
import numpy
from numpy import matrix
from numpy import zeros
import time

'''
EMMA-2: Evaluation method for comparing gold standard morpheme
analyses with predicted analyses for words in a word list.

Version: 1.0
Last modified: 2012-01-05

This program is based on EMMA.py (version 1.0) by Sebastian Spiegler.

    ----------------------------------------------------------------------
    Copyright (C) 2010-2012  Sami Virpioja <sami.virpioja@aalto.fi> and
                             Sebastian Spiegler <spiegler@cs.bris.ac.uk>

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

Evaluation is based on a hard assignment of gold standard morpheme
labels to predicted labels and v.v. This is achieved by performing a
"maximum matching of a bipartite graph" where the two partitions are
the gold standard and predicted labels.The objective function is based
on the number of words gold standard and predicted labels share. The
total sum of this number should be maximized for the global
assignment. This global assignment or maximum matching is found by
optimizing a linear program where all elements of the smaller of the
two partitions are matched with one of the other partition. For this,
the third party linear program solver lp_solve(^1) is used.

After the maximum matching of labels has been found, predicted labels
are exchanged by their gold standard matches. The evaluation is then
performed as a set comparison of gold standard analysis against
predicted analysis. The individual fraction added to the precision is
the number of common morphemes divided by the number of predicted
morphemes. The individual fraction of the recall is the number of
common morphemes divided by the number of gold standard morphemes. The
sum of all word fractions is then normalised by the number of words in
the list. The f-measure (F1) is calculated as the harmonic mean of
precision and recall. It equals 2*precision*recall /
(precision+recall).

The evaluation also considers alternative analyzes. Gold standard and
predicted alternatives are compared to each other on the basis of how
many morphemes each combination shares. Once again, a maximum matching
or hard assignment is calculated. The actual morpheme label comparison
is performed for assigned combinations and multiplied by the inverse
number of possible combinations.  In this way, giving too few or too
many alternatives is punished.

The EMMA-2 version allows assigning one reference (proposed) morpheme
to many proposed (reference) morphemes when estimating precision
(recall). Researchers using EMMA-2 are requested to refer to the
following article in their scientific publications:

  Sami Virpioja, Ville T. Turunen, Sebastian Spiegler, Oskar Kohonen,
  and Mikko Kurimo. Empirical comparison of evaluation methods for
  unsupervised learning of morphology. Traitement Automatique des
  Langues, 52(2), 2011.

The option --onetoone can be used to force one-to-one assignment
between the morphemes. However, the original EMMA.py is faster to for
this purpose.
 
(^1) source: http://lpsolve.sourceforge.net, lp_solve version 5.5.0.15, 
     Under GNU LESSER GENERAL PUBLIC LICENSE
According to Section 6 of this license our work is "work that uses the
Library" [lp_solve]. For running the evaluation script, lp_solve has
to be installed on the user's computer. An executable will be provided
with the evaluation script or can be acquired from the url stated
above.
'''
################################################################################
#
# Important variables
#
################################################################################

# Please state executable and path of lp_solve !!!
_lpSolvePath = "/share/morpho/rd/morfessor2005/evaluation/emma/bin/lp_solve"

################################################################################
#
# Class main_class
#
################################################################################
class main_class:
    #===========================================================================
    # main method 
    #===========================================================================
    @staticmethod
    def main(goldFile, predFile, saveAssign, saveResult, verbose, short, 
             onetomany):

        ts = time.time()

        # get predictions and gold standard
        predDict = main_class.findPredictions(goldFile, predFile)
        goldDict = main_class.readGoldStandard(goldFile)
        
        # morpheme assignment
        pid = os.getpid()
        lpInput  = predFile + ".lpInput1.%s" % pid
        lpOutput = predFile + ".lpOutput1.%s" % pid
        assignFile = predFile + ".assignment1"
        morphAssignDict1 = morphassignment.main(goldDict, predDict, 
                                                lpInput, lpOutput, 
                                                assignFile, saveAssign, 
                                                verbose, onetomany)
        # clean up
        if not onetomany:
            os.system("rm " + lpInput)
            os.system("rm " + lpOutput)
        
        lpInput  = predFile + ".lpInput2.%s" % pid
        lpOutput = predFile + ".lpOutput2.%s" % pid
        assignFile = predFile + ".assignment2"
        morphAssignDict2 = morphassignment.main(predDict, goldDict, 
                                                lpInput, lpOutput, 
                                                assignFile, saveAssign, 
                                                verbose, onetomany)
        
        # clean up
        if not onetomany:
            os.system("rm " + lpInput)
            os.system("rm " + lpOutput)
                
        # assignment evaluation
        tempFile = predFile + ".temp"
        resultFile = predFile + ".result"
        (precision, recall, fmeasure) = assigneval.main(goldDict, predDict, 
                                                        morphAssignDict1, 
                                                        morphAssignDict2, 
                                                        tempFile,
                                                        resultFile,
                                                        saveResult, verbose)
        te = time.time()
        if not short:
            print "\nRESULT:\n======="
            print "gold standard:", goldFile
            print "prediction   :", predFile
            print "evaluation time: %.2fs" % (te-ts)
            print
            print "precision:", precision
            print "recall   :", recall
            print "fmeasure :", fmeasure
        else:
            print str(precision) + "\t" + str(recall) + "\t" + str(fmeasure) 
        
        path = os.path.dirname(tempFile)
        if path == "":
            listing = os.listdir(".")
        else:
            listing = os.listdir(path)
        for f in listing:
            f = path + "/" + f
            if str(f).startswith(tempFile):
                os.system("rm " + f)
                #print f, "deleted"
        
    #===========================================================================
    # method which finds subset of predictions which also occur in gold standard
    #===========================================================================
    @staticmethod
    def findPredictions(goldFile, predFile):
        text_gold = open(goldFile, "r")
        goldLines = text_gold.readlines()
        text_gold.close()
    
        # gold standard words    
        goldWordSet = set()
        for goldLine in goldLines:
            split1 = goldLine.split("\t")
            word1 = split1[0]
            goldWordSet.add(word1)
        
        
        # prediction file
        predictionDict = dict() 
        for predLine in open(predFile,'r'):
            split2 = predLine.split("\t")
            word2 = split2[0]
            if goldWordSet.__contains__(word2):
                segmentationList = split2[1].split(",")
                lol = list()
                for segmentation in segmentationList:
                    segments = re.findall("[^\s]+", segmentation)
                    lol.append(segments)
                predictionDict[word2] = lol
        return predictionDict
    
    #===========================================================================
    # method which reads in gold standard file
    #===========================================================================
    @staticmethod
    def readGoldStandard(goldFile):
        # gold standard dictionary
        goldDict = dict() 
        for line in open(goldFile,'r'):
            split1 = line.split("\t")
            word = split1[0]
            segmentationList = split1[1].split(",")
            lol = list()
            for segmentation in segmentationList:
                segments = re.findall("[^\s]+", segmentation)
                lol.append(segments)
            goldDict[word] = lol
        return goldDict

################################################################################
#
# Class morphassignment       
# Step 1: global assignment of gold standard to predicted morphemes
#
################################################################################
class morphassignment:
    #===========================================================================
    # main method for assigning predicted to gold standard morphemes
    #===========================================================================
    @staticmethod
    def main(goldDict, predDict, lpInput, lpOutput, assignFile, saveAssign, verbose, onetomany=False):
        goldMorphIndex = morphassignment.wordSegmentationList2MorphIndex(goldDict)
        predMorphIndex = morphassignment.wordSegmentationList2MorphIndex(predDict)
        
        # calc countMatrix
        countMatrix = morphassignment.calcCountMatrix(goldDict, predDict, 
                                                      goldMorphIndex, 
                                                      predMorphIndex)
        
        #print goldMorphIndex
        #print predMorphIndex
        #print countMatrix

        if onetomany:
            #csum = 1.0 / countMatrix.sum(1)
            #normMat = numpy.mat(numpy.diag(numpy.array(csum)[:,0], 0)) * \
            #    countMatrix
            #countMatrix += 0.01 * normMat

            # one-to-many mapping is trivial: just take the maximums
            I = numpy.argmax(numpy.array(countMatrix), 0)
            morphAssignDict = {}
            for i in range(len(I)):
                morphAssignDict[predMorphIndex[i]] = goldMorphIndex[I[i]]
            #print morphAssignDict

        else:
            # input file for lp_solver generated
            morphassignment.writeLPInputFile(countMatrix, lpInput, 
                                             rowconst=(not onetomany))

            # solve morpheme assignment
            os.system(_lpSolvePath + " " + lpInput + " > " + lpOutput)
        
            # get morpheme assignment dictionary
            if verbose:
                print "\nMorpheme Assignment (gold standard => prediction)\n=================================================\n"
            morphAssignDict = morphassignment.getMorphAssignDict(goldMorphIndex, 
                                                                 predMorphIndex, 
                                                                 lpOutput, verbose)
            #print morphAssignDict

        # save assignment if flagged
        if saveAssign:
            morphassignment.saveMorphemeAssignment(morphAssignDict, assignFile)        

        # return assignment dictionary
        return morphAssignDict

    #===========================================================================
    # 
    #===========================================================================
    @staticmethod
    def saveMorphemeAssignment(morphAssignDict, assignFile):
        tempList = list()
        for pred in morphAssignDict.keys():
            gold = morphAssignDict[pred]
            tempList.append(gold + "\t=>\t" + pred + "\n")
        tempList = sorted(tempList)
        resultList = list()
        resultList.append("#############################################\n")
        resultList.append("# gold standard labels\t=>\tpredicted labels\n")
        resultList.append("#############################################\n")
        resultList.extend(tempList)
        
        f = open(assignFile, 'w')
        f.writelines(resultList)
        f.close() 
        
    #===========================================================================
    # method which generates morpheme index for gold standard/predictions 
    #===========================================================================
    @staticmethod
    def wordSegmentationList2MorphIndex(wordDict):
        morphList = list()
        for word in wordDict:
            segmentationList = wordDict[word]
            for segmentation in segmentationList:
                morphList.extend(segmentation)
        morphList = list(sorted(set(morphList)))
        return morphList

    #===========================================================================
    # method which calculates count matrix: if multiple analyzes exist for gold
    # standard or predictions, then fraction is added:
    # => 1/ (#gold standard analyzes * #predicted analyzes)
    #===========================================================================
    @staticmethod
    def calcCountMatrix(goldDict, predDict, goldMorphIndex, predMorphIndex):
        countMatrix = matrix(zeros((len(goldMorphIndex), 
                                    len(predMorphIndex))), dtype=float)
        # count matrix  
        for word in goldDict.keys():
            try:
                goldSegLoL = goldDict[word]
                predSegLoL = predDict[word]
                ratio = float(1) / (float(len(goldSegLoL)) * float(len(predSegLoL)))
                
                for gSegmentation in goldSegLoL:
                    for gSegment in gSegmentation:
                        row = list(goldMorphIndex).index(gSegment)
                        for pSegmentation in predSegLoL:
                            for pSegment in pSegmentation:
                                col = list(predMorphIndex).index(pSegment)
                                countMatrix = tools.incItem(countMatrix, 
                                                            row, col, ratio)
            # key error can occur when gold standard word cannot be found in predictions                                
            except KeyError:
                pass
        return countMatrix

    #===========================================================================
    # method which generates output for lp_solve
    #===========================================================================
    @staticmethod
    def writeLPInputFile(countMatrix, lpInput, rowconst=True):
        resultList = list()
        
        (rows, cols) = countMatrix.shape
        maxString = "max: " 
        binString = "bin "
    
        for r in range(rows):
            for c in range(cols):
                item = "b_" + str(r) + "_" + str(c)
                cost = tools.getItem(countMatrix, r, c) 
                maxString += str(cost) + " " + item  + " + "
                binString += item + ", "
        maxString = maxString[0:len(maxString)-3] +";"
        binString = binString[0:len(binString)-2] +";"
        
        rowConstraints = str()
        for r in range(rows):
            rconstraint = str()
            for c in range(cols):
                item = "b_" + str(r) + "_" + str(c)
                rconstraint += item + " + "
            rconstraint = rconstraint[0:len(rconstraint)-3] + " <= 1;"
            rowConstraints += rconstraint + "\n" 
        rowConstraints = re.sub("\n$", "", rowConstraints)
        
        colConstraints = str()
        for c in range(cols):
            cconstraint = str()
            for r in range(rows):
                item = "b_" + str(r) + "_" + str(c)
                cconstraint += item + " + "
            cconstraint = cconstraint[0:len(cconstraint)-3] + " <= 1;"
            colConstraints += cconstraint + "\n" 
        colConstraints = re.sub("\n$", "", colConstraints)
        
        resultList.append(maxString + "\n\n")
        if rowconst:
            resultList.append(rowConstraints + "\n\n")
        resultList.append(colConstraints + "\n\n")    
        resultList.append(binString + "\n\n")

        f = open(lpInput, 'w')
        f.writelines(resultList)
        f.close()    
    
    #===========================================================================
    # method which translates lp_solve output into morpheme assignment dict
    # morpheme assignment dict:    pred morpheme => gold standard morpheme
    #===========================================================================
    @staticmethod
    def getMorphAssignDict(goldMorphIndex, predMorphIndex, lpOutput, verbose):
        morphAssignDict = dict() 
        for line in open(lpOutput,'r'):
            line = re.sub('\n$', '', line)
            found = re.findall("^(\w+)\s+(\d+)$", line)
            if found:
                (assign, bit) = found[0]
                if int(bit) == 1:
                    split1 = assign.split("_")
                    i = int(split1[1])
                    j = int(split1[2])
                    goldM = goldMorphIndex[i]
                    predM = predMorphIndex[j]
                    morphAssignDict[predM] = goldM
                    
                    if verbose:
                        print goldM, "=>", predM
                    
        return morphAssignDict

################################################################################
#
# Class assigneval
# Step 2: mapping of morpheme assignment to predicted segmentations and 
# evaluation based on set comparison
#
################################################################################
    
class assigneval:
    #===========================================================================
    # main method which evaluates predictions based on morpheme assignment
    #===========================================================================
    @staticmethod
    def main(goldDict, predDict, morphAssignDict1, morphAssignDict2, tempFile, resultFile, saveResult, verbose):

        if verbose:
            print "\nAssignment evaluation: precision\n=====================\n"
            print morphAssignDict1

        precision_count = assigneval.eval_single(goldDict, predDict, morphAssignDict1, tempFile, resultFile, saveResult, verbose)

        if verbose:
            print "\nAssignment evaluation: recall\n=====================\n"
            print morphAssignDict2

        recall_count = assigneval.eval_single(predDict, goldDict, morphAssignDict2, tempFile, resultFile, saveResult, verbose)

        # get performance measures and return them
        (p, r, f) = assigneval.calcPerformanceMeasures(precision_count, recall_count, len(goldDict.keys()), verbose)
        return (p, r, f)


    @staticmethod
    def eval_single(goldDict, predDict, morphAssignDict, 
                    tempFile, resultFile, saveResult, verbose):
        pid = os.getpid()
        tempFile_lpInput = tempFile + ".lpInput.%s" % pid
        tempFile_lpOutput = tempFile + ".lpOutput.%s" % pid
        precision_count = float(0)

        exchangedOut = list()
        for word in goldDict.keys():
            try:
                goldSegmentationList = goldDict[word]
                predSegmentationList = predDict[word]
                goldNo = len(goldSegmentationList)
                predNo = len(predSegmentationList)
                
                try:
                    ratio_precision = float(1) / float(predNo)
                    
                    # simple evaluation
                    if goldNo == 1 and predNo == 1:
                        for goldSegmentation in goldSegmentationList:
                            for predSegmentation in predSegmentationList:
                                replacedPredSegm = assigneval.replaceLabels\
                                    (predSegmentation, morphAssignDict)
                            
                                # precision = intersection prediction, gold standard / size prediction
                                precision_fraction = ratio_precision * assigneval.list1ToList2Comparison(list(goldSegmentation), list(replacedPredSegm))
                                precision_count += precision_fraction
                
                                if verbose: print numpy.min([goldNo, predNo]), "alternative(s): p+=", precision_fraction, "gold:", goldSegmentation, "pred:",replacedPredSegm    
    
                                # add to result list of predicted segmentations with exchanged labels
                                exchangedOut.append(word + "\t" + 
                                                    tools.list2string(replacedPredSegm, " ") + "\n")
        
                    # segmentation assignment
                    else:
    
                        (segmentationAssignmentDict, countMatrix) = \
                            assigneval.calcCountMatrix_Segmentation\
                            (goldSegmentationList, predSegmentationList, 
                             morphAssignDict)
                        morphassignment.writeLPInputFile(countMatrix, 
                                                         tempFile_lpInput)
    
                        # solve morpheme assignment
                        os.system(_lpSolvePath + " " + tempFile_lpInput + " > " + tempFile_lpOutput)
    
                        # use assignment
                        exchangedStr = word + "\t"
                        for line in open(tempFile_lpOutput,'r'):
                            line = re.sub('\n$', '', line)
                            found = re.findall("^(\w+)\s+(\d+)$", line)
                            if found:
                                (assign, bit) = found[0]
                                
                                if int(bit) == 1:
                                    split1 = assign.split("_")
                                    i = int(split1[1])
                                    j = int(split1[2])
                                    key = str(i) + "_" + str(j)
                                    (goldSegmentation, replacedPredSegm) = segmentationAssignmentDict[key]
                                    
                                    # precision = intersection prediction, gold standard / size prediction
                                    precision_fraction = ratio_precision * assigneval.list1ToList2Comparison(list(goldSegmentation), list(replacedPredSegm))
                                    precision_count += precision_fraction
                
                                    if verbose: print numpy.min([goldNo, predNo]), "alternative(s): p+=", precision_fraction, "gold:", goldSegmentation, "pred:",replacedPredSegm
                                        
                                    exchangedStr += tools.list2string(replacedPredSegm, " ") + ", "
                    
                        # add to result list of predicted segmentations with exchanged labels
                        exchangedStr = exchangedStr[0:len(exchangedStr)-2]                
                        exchangedOut.append(exchangedStr + "\n")
                
                except ZeroDivisionError:
                    print word, "with gs:", goldSegmentationList, "and ps:", predSegmentationList, "was not evaluated"
                    pass
            
            # if gold standard word is not found in predictions, pass
            except KeyError:
                pass
        # write exchanged prediction
        if saveResult:
            f_out = open(resultFile, "w")
            f_out.writelines(sorted(exchangedOut))
            f_out.close()

        # clean up
        os.system("rm " + tempFile_lpInput)
        os.system("rm " + tempFile_lpOutput)

        return precision_count
    
    #===========================================================================
    # method calculates performance measures
    #===========================================================================
    @staticmethod
    def calcPerformanceMeasures(precision_count, recall_count, word_count, verbose):
        precision = float(precision_count) / float(word_count)
        recall = float(recall_count) / float(word_count)
        try: fmeasure = 2 * precision * recall / (precision + recall)
        except ZeroDivisionError: fmeasure = 0
        
        if verbose:
            print "\nCalculation of performance measures\n===================================\n"
            print "precision (p) = p count / word count =", precision_count, "/", word_count, "=", precision
            print "recall    (r) = r count / word count =", recall_count, "/", word_count, "=", recall
            print "f-measure (f) = 2 * p * r / (p + r)  =", fmeasure    
                     
        return (precision, recall, fmeasure)
     
    #===========================================================================
    # method which replaces predicted labels by assigned gold standard labels
    #===========================================================================
    @staticmethod
    def replaceLabels(predSegmentation, morphAssignDict):
        newList = list()
        assignmentSet = morphAssignDict.keys()
        for predLabel in predSegmentation:
            if assignmentSet.__contains__(predLabel):
                goldLabel = morphAssignDict[predLabel]
                newList.append(goldLabel)
            else:
                newList.append(predLabel)
        return newList

    #===========================================================================
    # method which performs set comparison of list1 to list2
    #===========================================================================
    @staticmethod
    def list1ToList2Comparison(list1, list2):
        list1 = list(list1)
        list2 = list(list2)
        found = 0
        list2Size = float(len(list2))
        for l in list2:
            if list1.__contains__(l):
                found += 1
        ratio = float(found) / list2Size
        return ratio

    #===========================================================================
    # 
    #===========================================================================
    @staticmethod
    def calcCountMatrix_Segmentation(goldSegmentationList, predSegmentationList, predGoldDict):
        countMatrix = matrix(zeros((len(goldSegmentationList), len(predSegmentationList))), dtype=float)
        segmentationAssignmentDict = dict()
        
        for i in range(len(goldSegmentationList)):
            goldSegmentation = goldSegmentationList[i]
            for j in range(len(predSegmentationList)):
                predSegmentation = predSegmentationList[j]
                replacedPredSegm = assigneval.replaceLabels(predSegmentation, predGoldDict)
                key = str(i) +"_" + str(j)
                segmentationAssignmentDict[key] = (goldSegmentation, replacedPredSegm)
                count = assigneval.list1ToList2Comparison(goldSegmentation, replacedPredSegm)
                countMatrix = tools.incItem(countMatrix, i, j, count)
        return (segmentationAssignmentDict, countMatrix)

################################################################################
#
# Class tools
#
################################################################################
class tools:
    ''' method which adds element to ordered dict key list '''
    @staticmethod
    def add2DictList(_dict, _key, _element):
        if _dict.__contains__(_key):
            _list = _dict[_key]
            _list.append(_element)
            _dict[_key] = _list
        else:
            _list = list()
            _list.append(_element)
            _dict[_key] = _list
        return _dict
    
    ''' method which increments key element by inc in ordered dict'''
    @staticmethod
    def incDict(_dict, _key, _inc):
        if _dict.__contains__(_key):
            _value = _dict[_key]
            _value += _inc
            _dict[_key] = _value
        else:
            _dict[_key] = _inc
        return _dict
    
    @staticmethod
    def getItem(m1, row, col):
        return m1.getA()[row][col]
        
    @staticmethod    
    def incItem(m1, row, col, inc):
        inc = float(inc)
        value = m1.getA()[row][col]
        value += inc
        m1.getA()[row][col] = value
        return m1
    
    @staticmethod
    def list2string(llist, delimiter):
        s = str()
        for l in llist:
            s += str(l) + delimiter
        s = s[0:len(s)-len(delimiter)]
        return s
################################################################################
#
# Option parser
#
################################################################################
if __name__ == "__main__":
    usage ="%prog -g goldFile -p predFile [-a save assignment -r save result -v verbose -s short result]"
    usage +="\n       Input files in format of Morpho Challenge results."
    usage +="\n       Example: word [tab] analysis 1[morpheme space]*, ..., analysis n\n"
    usage +="\nCopyright (C) 2010 Sebastian Spiegler, spiegler@cs.bris.ac.uk\nThis program is under GNU General Public License version 3.\nSee: <http://www.gnu.org/licenses/>.\n"
    usage +="\nEvaluation method for comparing gold standard morpheme analyses with predicted analyses for words in a word list.\n"
    parser = OptionParser(usage=usage, version="%prog 1.0a")
    parser.add_option("-g", "--goldFile", action="store", type="string", dest="goldFile", help="gold standard file")
    parser.add_option("-p", "--predFile", action="store", type="string", dest="predFile", help="prediction file")
    parser.add_option("-a", "--saveAssign", action="store_true", dest="saveAssign", help="flag for saving morpheme assignments")
    parser.add_option("-r", "--saveResult", action="store_true", dest="saveResult", help="flag for saving prediction file with gold standard morphemes labels")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help="verbose, prints out all information")
    parser.add_option("-s", "--short", action="store_true", dest="short", help="short result, prints precision, recall, f-measure separated by tab")
    parser.add_option("-1", "--onetoone", action="store_false", default=True, dest="onetomany", help="Force one-to-one mapping between morphs")

    (options, args) = parser.parse_args()
    if options.goldFile and options.predFile:
        goldFile=options.goldFile
        predFile=options.predFile
        saveAssign=options.saveAssign
        saveResult=options.saveResult
        verbose=options.verbose
        short=options.short
        onetomany=options.onetomany
        main_class.main(goldFile, predFile, saveAssign, saveResult, verbose, 
                        short, onetomany)
    else:
        parser.print_help()

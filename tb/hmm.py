#! /usr/bin/env python
"""
usage:
  tb hmm [--alt=<alt_sample>] <vcf>

Example

options:
  -h --help                   Show this screen.
  --version                   Show version.



"""
from docopt import docopt
from utils.vcf import *
from utils.fasta import *
from collections import defaultdict
import sys
from utils import autoconvert
from yahmm import *
import itertools
import numpy as np
from pprint import pprint as pp


# Setup hmm
model = Model( name="RIL_GT" )

ref = State( DiscreteDistribution({ 'ref': 0.97, 'alt': 0.03 }) )
alt = State( DiscreteDistribution({ 'ref': 0.03, 'alt': 0.97 }) )

model.add_transition( model.start, ref, 0.5 )
model.add_transition( model.start, alt, 0.5 )

# Transition matrix, with 0.05 subtracted from each probability to add to
# the probability of exiting the hmm
model.add_transition( ref, ref, 0.9998 )
model.add_transition( ref, alt, 0.0001 )
model.add_transition( alt, ref, 0.0001 )
model.add_transition( alt, alt, 0.9998 )

model.add_transition( ref, model.end, 0.0001 )
model.add_transition( alt, model.end, 0.0001 )

model.bake( verbose=True )

to_model = {0:'ref', 1: 'alt'}
from_model = {True: 0, False: 1}
GT_Class = {True: 0, False: 1}
GT = {True: 0, 'alt': 1}


class sample:
    def __init__(self, name):
        self.name = name


debug = None
if len(sys.argv) == 1:
    debug = ["hmm", "--alt=CB4856","../RIL_test.vcf.gz"]

if __name__ == '__main__':
    args = docopt(__doc__,
                  argv=debug,
                  options_first=False)

    vcf = vcf(args["<vcf>"])

    # Put genotypes into large array
    """
        0/0 -> 0
        0/1 -> 1
        ./. -> 2
        1/1 -> 3
    """
    gt_list = []
    chromosome = []
    positions = []

    print args
    if args["--alt"]:
        # Subset by sample
        alt_sample = args["--alt"]
        alt_sample_index = vcf.samples.index(alt_sample)
    append_gt = True
    for n, line in enumerate(vcf):
        if args["--alt"]:
            append_gt = (line.gt_types[alt_sample_index] == 3)
        if append_gt:
            chromosome.append(line.CHROM)
            positions.append(line.POS)
            gt_list.append(list(line.gt_types))
    gt_set = np.vstack([gt_list]).astype("int32")
    gt_set[gt_set == 1] = -1 # Het
    gt_set[gt_set == 2] = -1 # Missing
    gt_set[gt_set == 3] = 1 # Alt
    for sample, column in zip(vcf.samples, gt_set.T):
        sample_gt = zip(chromosome, positions, column)
        sample_gt = [x for x in sample_gt if x[2] in [0,1]]
        sequence = [to_model[x[2]] for x in sample_gt]
        if sequence:
            results = model.forward_backward( sequence )[1]
            result_gt = [from_model[x] for x in np.greater(results[:,0],results[:,1])]
            results = ((a,b,c,d) for (a,b,c),d in zip(sample_gt, result_gt))

            # Output results
            n = 0
            last_contig = "null"
            last_pred = -1
            for chrom, pos, orig, pred in results:
                if chrom != last_contig or pred != last_pred:
                    if n > 0:
                        out = '\t'.join(map(str,[contig, start, end, sample, last_pred]))
                        print(out)
                    contig = chrom
                    start = pos
                end = pos
                last_pred = pred
                last_contig = chrom
                last_pos = pos
                n += 1

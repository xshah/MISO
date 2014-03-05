##
## Test scoring functions
##
import os
import sys
import time
import unittest

import numpy as np
import numpy.linalg as linalg
import math

import scipy
import scipy.misc 
from scipy.special import gammaln

import misopy
import misopy.internal_tests
import misopy.internal_tests.py_scores as py_scores

import misopy.pyx
import misopy.pyx.miso_scores_single as scores_single
import misopy.pyx.miso_scores_paired as scores_paired
import misopy.pyx.miso_proposals as miso_proposals
import misopy.pyx.stat_helpers as stat_helpers
import misopy.pyx.math_utils as math_utils


num_inc = 3245
num_exc = 22
num_com = 39874
READS = [[1,0]] * num_inc + \
        [[0,1]] * num_exc + \
        [[1,1]] * num_com
READS = np.array(READS, dtype=np.dtype("i"))
read_len = 40
overhang_len = 4
num_parts_per_iso = np.array([3, 2], dtype=np.dtype("i"))
iso_lens = np.array([1253, 1172], dtype=np.dtype("i"))
# Assignment of reads to isoforms: assign half of
# the common reads to isoform 0, half to isoform 1
iso_nums = [0]*3245 + [1]*22 + [0]*19937 + [1]*19937
iso_nums = np.array(iso_nums, dtype=np.dtype("i"))
num_reads = len(READS)

def print_test(test_text):
    print "-" * 10
    print test_text
    

class TestScores(unittest.TestCase):
    """
    Test MISO scoring functions.
    """
    def setUp(self):
        self.reads = READS
        self.read_len = read_len
        self.overhang_len = overhang_len
        self.num_parts_per_iso = num_parts_per_iso
        self.iso_lens = iso_lens
        self.scaled_lens = self.iso_lens - read_len + 1
        self.log_num_reads_possible_per_iso = np.log(self.scaled_lens)
        self.iso_nums = iso_nums
        self.num_reads = len(self.reads)
        self.psi_vector = np.array([0.8, 0.2])
        # Compute log psi frag
        self.log_psi_frag = np.log(self.psi_vector) + np.log(self.scaled_lens)
        self.log_psi_frag = self.log_psi_frag - scipy.misc.logsumexp(self.log_psi_frag)
        self.num_parts_per_iso = num_parts_per_iso

        
    def test_log_score_reads(self):
        # Take the first two reads
        curr_num_reads = 2
        two_reads = self.reads[0:2]
        # Check identity of reads
        assert(np.array_equal(two_reads[0], np.array([1, 0])))
        assert(np.array_equal(two_reads[1], np.array([1, 0])))
        # Score the reads given an isoform assignment
        total_log_read_prob = \
          scores_single.sum_log_score_reads(two_reads,
                                            iso_nums[0:2],
                                            num_parts_per_iso,
                                            self.iso_lens,
                                            self.log_num_reads_possible_per_iso,
                                            curr_num_reads,
                                            self.read_len,
                                            self.overhang_len)
        # Compute it by hand: probability of a read is 1 / (# possible positions)
        log_prob_read_1 = np.log(1 / float(self.scaled_lens[iso_nums[0]]))
        log_prob_read_2 = np.log(1 / float(self.scaled_lens[iso_nums[1]]))
        print log_prob_read_1 + log_prob_read_2
        assert (total_log_read_prob == (log_prob_read_1 + log_prob_read_2)), \
           "Failed to score reads correctly."


    def approx_eq(self, p1, p2, error=0.0001):
        return (np.abs(p1 - p2) < error)


    def test_log_score_assignments(self):
        curr_num_reads = 2
        two_reads = self.reads[0:curr_num_reads]
        psi_frag_numer = \
          np.array([(self.scaled_lens[0] * self.psi_vector[0]),
                    (self.scaled_lens[1] * self.psi_vector[1])])
        psi_frag_denom = np.sum(psi_frag_numer)
        psi_frag = psi_frag_numer / psi_frag_denom
        assert self.approx_eq(sum(psi_frag), 1.0), "Psi frag does not sum to 1."
        assert (self.approx_eq(self.log_psi_frag[0], np.log(psi_frag)[0])), \
          "Log psi frag not set properly."
        log_assignments_prob = np.empty(2, dtype=float)
        total_log_assignments_prob = \
          scores_single.sum_log_score_assignments(self.iso_nums[0:curr_num_reads],
                                                  self.log_psi_frag,
                                                  curr_num_reads,
                                                  log_assignments_prob)
        # Compute the probability of assignments
        manual_result = (np.log(psi_frag[self.iso_nums[0]]) + \
                         np.log(psi_frag[self.iso_nums[1]]))
        assert (self.approx_eq(manual_result, total_log_assignments_prob)), \
          "Failed to score assignments correctly."


    def test_my_logsumexp(self):
        vals_to_test = [np.array([-1462.26, -1 * np.inf]),
                        np.array([0.1, 0.5])]
        for v in vals_to_test:
            scipy_result = scipy.misc.logsumexp(v)
            result = math_utils.my_logsumexp(v, len(v))
            assert (self.approx_eq(scipy_result, result)), \
              "My logsumexp failed on %s" %(str(v))


    def test_sample_reassignment(self):
        curr_num_reads = 200
        subset_reads = self.reads[0:curr_num_reads]
        psi_frag_numer = \
          np.array([(self.scaled_lens[0] * self.psi_vector[0]),
                    (self.scaled_lens[1] * self.psi_vector[1])])
        psi_frag_denom = np.sum(psi_frag_numer)
        psi_frag = psi_frag_numer / psi_frag_denom
        log_psi_frag = np.log(psi_frag)
        result = np.empty(curr_num_reads, dtype=np.dtype("i"))
        result = scores_single.sample_reassignments(subset_reads,
                                                    self.psi_vector,
                                                    log_psi_frag,
                                                    self.log_num_reads_possible_per_iso,
                                                    self.scaled_lens,
                                                    self.iso_lens,
                                                    self.num_parts_per_iso,
                                                    self.iso_nums[0:curr_num_reads],
                                                    curr_num_reads,
                                                    self.read_len,
                                                    self.overhang_len,
                                                    result)


    def test_init_assignments(self):
        reads = self.reads
        assignments = scores_single.init_assignments(self.reads,
                                                     self.num_reads,
                                                     2)


    def test_logistic_normal_log_pdf(self):
        print_test("Testing logistic normal log pdf")
        theta = np.array([0.5, 0.5])
        mu = np.array([0.8])
        num_isoforms = 2
        proposal_diag = 0.05
        sigma = py_scores.set_diag(np.zeros((num_isoforms-1, num_isoforms-1)),
                                   proposal_diag)
        result_pyx = stat_helpers.logistic_normal_log_pdf(theta[:-1],
                                                          mu,
                                                          proposal_diag)
        print "Logistic normal log pdf Cython: "
        print result_pyx
        print "Logistic normal log pdf Python: "
        result_original = py_scores.original_logistic_normal_log_pdf(theta, mu, sigma)
        print result_original
        assert (py_scores.approx_eq(result_pyx, result_original)), \
          "Error computing logistic normal log pdf."


    def test_single_end_joint_score(self):
        """
        Test single-end joint score.
        """
        curr_num_reads = 2
        two_reads = self.reads[0:curr_num_reads]
        psi_frag_numer = \
          np.array([(self.scaled_lens[0] * self.psi_vector[0]),
                    (self.scaled_lens[1] * self.psi_vector[1])])
        psi_frag_denom = np.sum(psi_frag_numer)
        psi_frag = psi_frag_numer / psi_frag_denom
        assert self.approx_eq(sum(psi_frag), 1.0), "Psi frag does not sum to 1."
        assert (self.approx_eq(self.log_psi_frag[0], np.log(psi_frag)[0])), \
          "Log psi frag not set properly."
        log_assignments_prob = np.empty(2, dtype=float)
        num_reads = len(self.reads)
        assignment_scores = np.empty(num_reads, dtype=float)
        num_isoforms = len(self.psi_vector)
        hyperparameters = np.array([1] * num_isoforms, dtype=float)
        overhang_len = 1
        # assignments set A: consistent set of reads to isoform
        # assignments
        iso_nums_A = self.iso_nums
        joint_score_A = \
          scores_single.log_score_joint_single_end(self.reads,
                                                   iso_nums_A,
                                                   self.psi_vector,
                                                   self.log_psi_frag,
                                                   assignment_scores,
                                                   num_parts_per_isoform,
                                                   iso_lens,
                                                   log_num_reads_possible_per_iso,
                                                   self.read_len,
                                                   num_reads,
                                                   hyperparameters,
                                                   overhang_len=overhang_len)
        # assignments set B: inconsistent set of reads to isoform
        # assignments
        joint_score_B = None
        # Here compare joint_A to joint_B ...
        # ...


def main():
    unittest.main()


if __name__ == "__main__":
    main()


import numpy as np
import os
import unittest
from medaka.features import FeatureEncoder, pileup_counts
from medaka.common import Region

__reads_bam__ = os.path.join(os.path.dirname(__file__), 'data', 'test_reads.bam')
__two_type_bam__ = os.path.join(os.path.dirname(__file__), 'data', 'test_two_type.bam')
__gapped_bam__ = os.path.join(os.path.dirname(__file__), 'data', 'reads_gapped.bam')
__region__ = Region('Consensus_Consensus_Consensus_Consensus_utg000001l', start=50000, end=100000)
__region_start__ = Region('Consensus_Consensus_Consensus_Consensus_utg000001l', start=0, end=200)

__kwargs__ = {
    'consensus_as_ref': False,
    'is_compressed': False,
    'log_min': None,
    'max_hp_len': 1,
    'normalise': 'total',
    'ref_mode': None,
    'with_depth': False
}

class CountsTest(unittest.TestCase):

    def test_001_basic_counting(self):

        # py-style
        kwargs = __kwargs__.copy()
        kwargs['normalise'] = None   # change this just for simple comparison
        encoder = FeatureEncoder(**kwargs)
        sample = encoder.bam_to_sample(__reads_bam__, __region__, reference=None, read_fraction=None, force_py=True)
        sample = sample[0]
        assert tuple(sample.positions.shape) == (81730,)
        assert tuple(sample.positions[0]) == (50000, 0)
        assert tuple(sample.positions[-1]) == (99999, 1)
        assert sample.features.shape == (81730, 10)
        # test counts
        np.testing.assert_array_equal(sample.features[0], np.array([ 0, 21, 0, 1, 0, 14, 0, 0, 0, 0]))
        # test mean depth
        np.testing.assert_almost_equal(np.mean(np.sum(sample.features, axis=1)), 19.83684081732534)


    def test_001_basic_counting_with_c(self):
        kwargs = __kwargs__.copy()
        kwargs['normalise'] = None   # change this just for simple comparison
        encoder = FeatureEncoder(**kwargs)
        sample = encoder.bam_to_sample_c(__reads_bam__, __region__)
        sample = sample[0]
        assert sample.positions.shape == (81730,)
        assert tuple(sample.positions[0]) == (50000, 0)
        assert tuple(sample.positions[-1]) == (99999, 1)
        assert tuple(sample.features.shape) == (81730, 10)
        # test counts
        np.testing.assert_array_equal(sample.features[0], np.array([ 0, 21, 0, 1, 0, 14, 0, 0, 0, 0]))
        # test mean depth
        np.testing.assert_almost_equal(np.mean(np.sum(sample.features, axis=1)), 19.83996084669032)


    def test_003_c_same_as_python(self):
        kwargs = __kwargs__.copy()
        kwargs['normalise'] = None   # change this just for simple comparison
        encoder = FeatureEncoder(**kwargs)
        sample_py = encoder.bam_to_sample(__reads_bam__, __region__, reference=None, read_fraction=None, force_py=True)
        sample_py = sample_py[0]
        sample_c = encoder.bam_to_sample_c(__reads_bam__, __region__)
        sample_c = sample_c[0]

        # it seems the pysam implementation does not include counts of bases
        # where the last aligned base follows an insertion
        # i.e. the last base in GGCTGATT*A is included in the c code, but
        # missing in the pysam counts. This happens 255 times over 81730 columns
        np.testing.assert_array_equal(sample_py.features[:226], sample_c.features[:226])

        d_c = np.sum(sample_c.features, axis=1)
        d_p = np.sum(sample_py.features, axis=1)
        assert len(d_c) == 81730
        assert len(np.where(np.not_equal(d_c, d_p))[0]) == 255


    def test_004_c_same_as_python_from_start(self):
        # check we get same when starting from 0 to make sure 0-based/1-based behaviour is same
        kwargs = __kwargs__.copy()
        kwargs['normalise'] = None   # change this just for simple comparison
        encoder = FeatureEncoder(**kwargs)
        sample_py = encoder.bam_to_sample(__reads_bam__, __region_start__, reference=None, read_fraction=None, force_py=True)
        sample_py = sample_py[0]
        sample_c = encoder.bam_to_sample_c(__reads_bam__, __region_start__)
        sample_c = sample_c[0]

        np.testing.assert_array_equal(sample_py.positions, sample_c.positions)
        np.testing.assert_array_equal(sample_py.features, sample_c.features)


    def test_005_c_same_as_python_norm_total(self):
        kwargs = __kwargs__.copy()
        kwargs['normalise'] = 'total'   # change this just for simple comparison
        encoder = FeatureEncoder(**kwargs)
        sample_py = encoder.bam_to_sample(__reads_bam__, __region__, reference=None, read_fraction=None, force_py=True)
        sample_py = sample_py[0]
        sample_c = encoder.bam_to_sample_c(__reads_bam__, __region__)
        sample_c = sample_c[0]

        # it seems the pysam implementation does not include counts of bases
        # where the last aligned base follows an insertion
        # i.e. the last base in GGCTGATT*A is included in the c code, but
        # missing in the pysam counts. This happens 255 times over 81730 columns
        np.testing.assert_array_almost_equal(sample_py.features[:226], sample_c.features[:226])

        d_c = np.sum(sample_c.features, axis=1)
        d_p = np.sum(sample_py.features, axis=1)
        expected_norm_depth = np.array([1., 1., 0.02777778, 1., 1., 0.05555556, 0.02777778, 1., 1., 0.02777778])
        np.testing.assert_array_almost_equal(d_c[:10], expected_norm_depth)
        np.testing.assert_array_almost_equal(d_p[:10], expected_norm_depth)

        rev_inds = [i for i, (dtype, is_rev, base, run_len) in enumerate(encoder.encoding) if is_rev]
        expected_rev_norm_depth = np.array([0.6111111,  0.6111111, 0.02777778, 0.61111116, 0.6111111 ,
                                            0.02777778, 0.,        0.6111111 , 0.61111116, 0.02777778])
        np.testing.assert_almost_equal(sample_c.features[:10, (rev_inds)].sum(axis=1), expected_rev_norm_depth)
        np.testing.assert_almost_equal(sample_py.features[:10, (rev_inds)].sum(axis=1), expected_rev_norm_depth)

        fwd_inds = [i for i, (dtype, is_rev, base, run_len) in enumerate(encoder.encoding) if not is_rev]
        expected_fwd_norm_depth = np.array([0.3888889 , 0.3888889 , 0.        , 0.3888889 , 0.3888889 ,
                                            0.02777778, 0.02777778, 0.38888893, 0.3888889 , 0.        ])
        np.testing.assert_almost_equal(sample_c.features[:10, (fwd_inds)].sum(axis=1), expected_fwd_norm_depth)
        np.testing.assert_almost_equal(sample_py.features[:10, (fwd_inds)].sum(axis=1), expected_fwd_norm_depth)


    def test_006_c_same_as_python_norm_fwd_rev(self):
        kwargs = __kwargs__.copy()
        kwargs['normalise'] = 'fwd_rev'   # change this just for simple comparison
        encoder = FeatureEncoder(**kwargs)
        sample_py = encoder.bam_to_sample(__reads_bam__, __region__, reference=None, read_fraction=None, force_py=True)
        sample_py = sample_py[0]

        d_p = np.sum(sample_py.features, axis=1)
        expected_norm_depth = np.array([2.        , 1.9999999 , 0.04545455, 2.        , 2.        ,
                                        0.11688312, 0.07142857, 2.        , 2.        , 0.04545455])
        np.testing.assert_array_almost_equal(d_p[:10], expected_norm_depth)

        rev_inds = [i for i, (dtype, is_rev, base, run_len) in enumerate(encoder.encoding) if is_rev]
        expected_rev_norm_depth = np.array([1.        , 1.        , 0.04545455, 1.        , 1.        ,
                                            0.04545455, 0.        , 1.        , 1.        , 0.04545455])
        np.testing.assert_almost_equal(sample_py.features[:10, (rev_inds)].sum(axis=1), expected_rev_norm_depth)

        fwd_inds = [i for i, (dtype, is_rev, base, run_len) in enumerate(encoder.encoding) if not is_rev]
        expected_fwd_norm_depth = np.array([1.        , 1.        , 0.        , 1.        , 1.        ,
                                            0.07142857, 0.07142857, 1.        , 1.        , 0.        ])
        np.testing.assert_almost_equal(sample_py.features[:10, (fwd_inds)].sum(axis=1), expected_fwd_norm_depth)


class CountsSplittingTest(unittest.TestCase):

    def test_000_split_gap(self):
        # The gapped bam has:
        # @SQ    SN:ref    LN:30
        # seq1    0    ref    1    7    10M
        # seq2    0    ref    15    13    16M
        # so an alignment from [0:10] and one from [14:30] without insertions
        chunk_lengths = [10, 16]

        region = Region.from_string('ref:0-30')
        results = pileup_counts(region, __gapped_bam__)
        self.assertEqual(len(results), 2, 'Number of chunks from gapped alignment')
        for exp_len, chunk in zip(chunk_lengths, results):
            for i in (0, 1):
                # check both pileup and positions
                self.assertEqual(exp_len, len(chunk[i]))

if __name__ == '__main__':
    unittest.main()

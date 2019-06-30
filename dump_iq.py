#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from gnuradio import analog
from gnuradio import audio
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio import filter
from gnuradio import gr
from gnuradio.eng_option import eng_option
from gnuradio.filter import firdes
from optparse import OptionParser
from fractions import gcd
import osmosdr
import time
import sys


class top_block(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "BiG dump")

        usage = "usage: %prog [options] iqfile"
        parser = OptionParser(option_class=eng_option, usage=usage)
        parser.add_option("-f", "--frequency", type="eng_float", default=None,
                          help="Set frequency of wanted signal", metavar="FREQ")
        parser.add_option("-s", "--sample_rate", type="eng_float", default=2048000,
                          help="Sampling rate of sdr [default: %default]", metavar="SR")
        parser.add_option("-a", "--audio", type="string", default=None,
                help="Specify alsa audio device for NBFM demodulation"
                "[my: plughw:CARD=He,DEV=0]")

        (options, args) = parser.parse_args()
        if len(args) > 0:
            iq_file=args[0]
        else:
            iq_file=None

        self.iq_file = iq_file
        self.audio_dev = options.audio

        if options.frequency is None:
            print "Frequency not set, use -f --frequency"
            sys.exit(1)

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = options.sample_rate
        self.offset = offset = 200000
        self.freq = freq = options.frequency
        self.decim = decim = samp_rate // 200000

        self.taps1 = taps1 = firdes.low_pass(10.0, samp_rate, 100000, 15000, firdes.WIN_HAMMING, 6.76)

        self.rf_amp = rf_amp = 14
        self.rate = rate = samp_rate / decim
        self.if_amp = if_amp = 40
        self.center_freq = center_freq = freq - offset
        self.bb_amp = bb_amp = 24

        self.sq_level = sq_level = -49

        self.audio_samp_rate = audio_samp_rate = 48000
        common_div = gcd (rate, audio_samp_rate)
        self.audio_decim = audio_decim = rate / common_div
        self.audio_inter = audio_inter = audio_samp_rate / common_div


        print 'Frequency desired  =','%d' % freq
        print 'Center frequency =', '%d' % center_freq
        print
        print 'Sample rate =', '%d' % samp_rate
        print 'Decimation factor =', '%d' % decim
        print 'IQ rate =', '%d' % rate
        print
        print 'Audio sample rate =', '%d' % audio_samp_rate
        print 'Audio Decimation =', '%d' % audio_decim
        print 'Audio Interpolation =', '%d' % audio_inter
        if iq_file is not None:
            print 'Save IQ =', '%s' % iq_file
        if self.audio_dev is not None:
            print 'Play NBFM demodulation on =', '%s' % self.audio_dev

        ##################################################
        # Blocks
        ##################################################
        self.src = osmosdr.source( args="numchan=" + str(1) + " " + 'driver=sdrplay,soapy=1,verbose=1' )
        self.src.set_sample_rate(samp_rate)
        self.src.set_center_freq(center_freq, 0)
        self.src.set_freq_corr(0, 0)
        self.src.set_dc_offset_mode(0, 0)
        self.src.set_iq_balance_mode(0, 0)
        self.src.set_gain_mode(False, 0)
        #self.src.set_gain(rf_amp, 0)
        #self.src.set_if_gain(if_amp, 0)
        #self.src.set_bb_gain(bb_amp, 0)
        #self.src.set_antenna('', 0)
        #self.src.set_bandwidth(0, 0)

        gain_names = self.src.get_gain_names()
        for name in gain_names:
            range = self.src.get_gain_range(name)
            print "%s gain range: start %d stop %d step %d" % (name, range.start(), range.stop(), range.step())

        self.src.set_gain(30, 'IFGR')
        self.src.set_gain(0, 'RFGR')

        for name in gain_names:
            print "%s Gain set to: %d" % (name, self.src.get_gain(name))

        if iq_file is not None:
            self.iq_sink = blocks.file_sink(gr.sizeof_gr_complex*1, iq_file, False)
            self.iq_sink.set_unbuffered(True)

        self.fir = filter.freq_xlating_fir_filter_ccc(int(decim), (taps1), offset, samp_rate)

        if self.audio_dev is not None:
            self.audio_sink = audio.sink(audio_samp_rate, self.audio_dev, True)
            self.audio_resampler = filter.rational_resampler_ccc(
                interpolation=int(audio_inter),
                decimation=int(audio_decim),
                taps=None,
                fractional_bw=None,
            )
            self.squelch = analog.pwr_squelch_cc(sq_level, 0.001, 10, True)
            self.nbfm = analog.nbfm_rx(
                audio_rate=audio_samp_rate,
                quad_rate=audio_samp_rate,
                tau=75e-6,
                max_dev=5e3,
            )


        ##################################################
        # Connections
        ##################################################

        if self.audio_dev is not None:
            self.connect((self.audio_resampler, 0), (self.squelch, 0))
            self.connect((self.fir, 0), (self.audio_resampler, 0))
            self.connect((self.nbfm, 0), (self.audio_sink, 0))
            self.connect((self.squelch, 0), (self.nbfm, 0))

        if iq_file is not None:
            self.connect((self.fir, 0), (self.iq_sink, 0))

        self.connect((self.src, 0), (self.fir, 0))


def main(top_block_cls=top_block, options=None):

    tb = top_block_cls()
    tb.start()
    tb.wait()


if __name__ == '__main__':
    main()

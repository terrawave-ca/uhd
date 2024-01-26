import numpy as np
import matplotlib.pyplot as plt

# @todo: make this into a class and have waveform type selectable


def sine(ampl, wave_freq, rate, ret_time_samples=False):
    num_cycles = 10
    n = np.arange(int(num_cycles * np.floor(rate / wave_freq)))
    data = ampl * np.exp(n * 2j * np.pi * wave_freq / rate)

    if ret_time_samples:
        return data, n
    else:
        return data


def dc_chirp(ampl, bw, fs, duration, pad_length: int = 4096, ret_time_samples=False):
    num_samples = int(fs * duration)

    t = np.linspace(-duration / 2, duration / 2, num=num_samples)
    chirp = ampl * np.array(
        np.exp(1j * np.pi * 0.5 * (bw / t[-1]) * (t**2)), dtype=np.complex64
    )

    if pad_length > 0:
        chirp = np.pad(chirp, pad_length, "constant", constant_values=(0))
        t = 1 / fs * np.arange(0, num_samples + pad_length * 2)

    if ret_time_samples:
        return chirp, t
    else:
        return chirp


def chirp(fs_Hz, T_s, f0_Hz, f1_Hz, periods=1, phase_rad=0, ret_time_samples=False):
    c = (f1_Hz - f0_Hz) / T_s  # Chirp rate in Hz/s.
    n = int(fs_Hz * T_s)  # Samples per repetition.
    t_s = np.linspace(0, T_s, n)  # Chirp sample times.

    # Phase, phi_Hz, is integral of frequency, f(t) = ct + f0.
    phi_Hz = (c * t_s**2) / 2 + (f0_Hz * t_s)  # Instantaneous phase.
    phi_rad = 2 * np.pi * phi_Hz  # Convert to radians.
    phi_rad += phase_rad  # Offset by user-specified initial phase.
    if ret_time_samples:
        return np.tile(np.exp(1j * phi_rad), periods), t_s
    else:
        return np.tile(np.exp(1j * phi_rad), periods)  # Complex I/Q.


if __name__ == "__main__":
    num_samples = 2e3
    ampl = 0.3
    wave_freq = 1e4
    sine_rate = 1e6
    chirp_sampling_rate = 20e6
    chirp_bw = 8e6  # (2e9 - 800e6) / 2
    chirp_duration = 1e-4  # [seconds]

    # w1, t1 = sine(ampl, wave_freq, sine_rate, ret_time_samples=True)

    # t = 1/fs * np.arange(0, num_samples)
    # waveform = scipy_chirp(t, f0=800e6, f1=2e9, t1=t[-100], method='linear')

    # w2, t2 = chirp(5e9, 5e5, 800e6, 2e9, ret_time_samples=True)
    w1, t1 = dc_chirp(
        ampl,
        chirp_bw,
        chirp_sampling_rate,
        chirp_duration,
        ret_time_samples=True,
    )
    w2, t2 = dc_chirp(
        ampl,
        chirp_bw,
        chirp_sampling_rate,
        chirp_duration / 2,
        ret_time_samples=True,
    )
    w3, t3 = dc_chirp(
        ampl,
        chirp_bw,
        chirp_sampling_rate,
        chirp_duration / 3,
        ret_time_samples=True,
    )

    # plt.figure(1)
    # plt.plot(t1, np.real(w1))
    # plt.plot(t1, np.imag(w1))
    # plt.xlabel("Time [Samples]")

    # plt.figure(2)
    # w1_fd = np.fft.fft(w1)
    # freqs = np.fft.fftfreq(len(w1_fd), d=t1[1] - t1[0])
    # plt.plot(freqs / 1e6, np.abs(w1_fd))
    # plt.xlabel("Freq [MHz]")

    plt.figure(3)
    plt.plot(t1, np.real(w1))
    plt.plot(t2, np.real(w2))
    plt.plot(t3, np.real(w3))
    # plt.plot(t2, np.imag(w2))
    plt.xlabel("Time [s]")

    plt.figure(4)
    w1_fd = np.fft.fft(w1)
    w2_fd = np.fft.fft(w2)
    w3_fd = np.fft.fft(w3)
    f1 = np.fft.fftfreq(len(w1_fd), d=t1[1] - t1[0])
    f2 = np.fft.fftfreq(len(w2_fd), d=t2[1] - t2[0])
    f3 = np.fft.fftfreq(len(w3_fd), d=t3[1] - t3[0])
    plt.plot(f1 / 1e6, np.abs(w1_fd))
    plt.plot(f2 / 1e6, np.abs(w2_fd))
    plt.plot(f3 / 1e6, np.abs(w3_fd))
    plt.xlabel("Freq [MHz]")
    plt.show()


#     def get_chirp(num_channels, sample_rate):
#     """
#     create the chirp signal to be transmitted
#     @todo: tune parameters
#     """

#     # Set up chirp parameters
#     # freq band: 0.8-2 GHz
#     # ramp speed, min and max freqs and output filename should be variable
#     fs = sample_rate
#     bw = 0.5e6
#     chirp_len = 10e3
#     t = 1/fs * (np.arange(0, chirp_len-1) - chirp_len/2)
#     chirp = np.array(np.exp(1j*np.pi*0.5*(bw/t[-1])*(t**2)), dtype=np.complex64)

#     num_zeros = 1024
#     tx_buf = np.zeros((num_channels, int(chirp_len+2*num_zeros)-1), dtype=np.complex64)
#     for ii in range(num_channels):
#         tx_buf[ii] = np.pad(chirp, num_zeros, 'constant', constant_values=(0))

#     return tx_buf

# def get_sine(ampl, wave_freq, rate):
#     waveforms = {
#         "sine": lambda n, wave_freq, rate: np.exp(n * 2j * np.pi * wave_freq / rate),
#         # "square": lambda n, wave_freq, rate: np.sign(waveforms["sine"](n, wave_freq, rate)),
#         # "const": lambda n, wave_freq, rate: 1 + 1j,
#         # "ramp": lambda n, wave_freq, rate:
#         #         2*(n*(wave_freq/rate) - np.floor(float(0.5 + n*(wave_freq/rate))))
#     }

#     data = np.array(
#         list(map(lambda n: ampl * waveforms["sine"](n, wave_freq, rate),
#             np.arange(
#                 int(10 * np.floor(rate / wave_freq)),
#                 dtype=np.complex64))),
#         dtype=np.complex64)  # One period
#     return data
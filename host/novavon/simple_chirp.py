import uhd
import argparse
import logging
import numpy as np
import sys
import threading
from typing import Any, List

from scipy.io import savemat

from utilities import LogFormatter
from utilities import LogFormatter
from waveforms import dc_chirp
from usrp_settings import usrp_setup


def rx_worker(usrp, rx_streamer, rx_statistics, rx_data):
    """Receive a fixed number of samples and store in rx_data"""

    # Make a receive buffer
    num_channels: int = rx_streamer.get_num_channels()
    total_samples: int = np.size(rx_data, 1)
    num_samples_per_packet: int = int(rx_streamer.get_max_num_samps())
    metadata = uhd.types.RXMetadata()
    recv_buffer: np.ndarray = np.zeros(
        (num_channels, num_samples_per_packet), dtype=np.complex64
    )
    assert num_channels == np.size(rx_data, 0)
    # Craft and send the Stream Command
    # continuous capture:
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)

    # capture a fixed num of samples
    # @todo: probably want this option in future
    # stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    # stream_cmd.num_samps = rx_num_samps

    stream_cmd.stream_now = num_channels == 1
    stream_cmd.time_spec = uhd.types.TimeSpec(
        usrp.get_time_now().get_real_secs() + RX_DELAY
    )
    rx_streamer.issue_stream_cmd(stream_cmd)

    num_rx_samps: int = 0

    # Receive until set number of samples are captured
    for ii in range(total_samples // num_samples_per_packet):
        try:
            samps = rx_streamer.recv(recv_buffer, metadata)

            rx_data[:, ii * num_samples_per_packet : (ii + 1) * num_samples_per_packet] = recv_buffer[:, 0:num_samples_per_packet]
            num_rx_samps += int(samps) * num_channels

        except RuntimeError as ex:
            logger.error("Runtime error in receive: %s", ex)
            return

    # Return the statistics to the main thread
    rx_statistics["num_rx_samps"] = num_rx_samps

    # After we get the signal to stop, issue a stop command
    rx_streamer.recv(recv_buffer, metadata)
    rx_streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))



def tx_worker(usrp, tx_streamer, tx_statistics, transmit_buffer):
    """Stream data stored in transmit_buffer"""

    # assert len(transmit_buffer) <= tx_streamer.get_max_num_samps()

    # Make a transmit buffer
    num_channels = tx_streamer.get_num_channels()
    metadata = uhd.types.TXMetadata()
    metadata.start_of_burst = True
    metadata.end_of_burst = False
    metadata.has_time_spec = bool(num_channels) #False
    metadata.time_spec = uhd.types.TimeSpec(usrp.get_time_now().get_real_secs() + TX_DELAY)

    # Transmit a fixed number of samples
    num_cycles = 10
    total_num_samps = np.size(transmit_buffer, 1) * num_cycles
    num_tx_samps = 0
    num_acc_samps = 0
    while num_acc_samps < total_num_samps:
        num_tx_samps += tx_streamer.send(transmit_buffer, metadata)
        num_acc_samps += min(
            total_num_samps - num_acc_samps, tx_streamer.get_max_num_samps()
        )
        # metadata.has_time_spec = False
        metadata.start_of_burst = False

    tx_statistics["num_tx_samps"] = num_tx_samps

    # Send a mini EOB packet
    metadata.end_of_burst = True
    tx_streamer.send(np.zeros((num_channels, 0), dtype=np.complex64), metadata)


def print_statistics(rx_statistics, tx_statistics):
    """Print TRX statistics in a formatted block"""

    statistics_msg = """
    Num received samples:     {}
    Num transmitted samples:  {}
    """.format(
        rx_statistics.get("num_rx_samps", 0), tx_statistics.get("num_tx_samps", 0)
    )
    logger.info(statistics_msg)


def start_threads(usrp, tx_buf, rx_buf):
    # @TODO: make this able to take in more general tx and rx workers
    cpu_sample_mode = "fc32"
    otw_sample_mode = "sc16"

    threads: List[threading.Thread] = []

    rx_statistics: dict[str, int] = {}
    st_args = uhd.usrp.StreamArgs(cpu_sample_mode, otw_sample_mode)
    st_args.channels = [0, 1]
    rx_streamer = usrp.get_rx_stream(st_args)
    rx_thread = threading.Thread(
        target=rx_worker, args=(usrp, rx_streamer, rx_statistics, rx_buf)
    )
    threads.append(rx_thread)
    rx_thread.setName("rx_stream")

    tx_statistics = {}
    st_args = uhd.usrp.StreamArgs(cpu_sample_mode, otw_sample_mode)
    st_args.channels = [0, 1]
    tx_streamer = usrp.get_tx_stream(st_args)
    tx_thread = threading.Thread(
        target=tx_worker, args=(usrp, tx_streamer, tx_statistics, tx_buf)
    )
    threads.append(tx_thread)
    tx_thread.setName("tx_stream")

    rx_thread.start()
    tx_thread.start()

    for thr in threads:
        thr.join()

    return tx_buf, rx_buf, tx_statistics, rx_statistics


def generate_output(args, tx_data, rx_data, tx_stats, rx_stats):
    if args.get("output_filename", ""):
        filename = args["output_filename"]
        if args["verbose"]:
            logger.info("Acquisition complete! Writing to file...")

        savemat(filename, {"data": rx_data})
        logger.info(f"Data written to {filename}")

    if args["plot_data"]:
        if args["verbose"]:
            logger.info("Plotting received data...")

        time_vec_tx = 1 / args["sampling_rate"] * np.arange(0, np.size(tx_data,1))
        time_vec_rx = 1 / args["sampling_rate"] * np.arange(0, np.size(rx_data,1))

        import matplotlib.pyplot as plt

        plt.figure()
        plt.plot(time_vec_tx * 1e6, np.real(tx_data[0,:]))
        plt.plot(time_vec_tx * 1e6, np.real(tx_data[1,:]))
        plt.plot(time_vec_rx * 1e6, np.real(rx_data[0,:])-0.1)
        plt.plot(time_vec_rx * 1e6, np.real(rx_data[1,:]+0.1))
        plt.xlabel("Time [us]")
        plt.legend(["Tx1", "Tx2", "Rx1", "Rx2"])

        # Plot frequency-domain data
        tx1_fd = np.fft.fft(tx_data[0, :])
        tx2_fd = np.fft.fft(tx_data[1, :])
        freqs_tx = np.fft.fftfreq(len(tx1_fd), d=time_vec_tx[1] - time_vec_tx[0])
        rx1_fd = np.fft.fft(rx_data[0, :])
        rx2_fd = np.fft.fft(rx_data[1, :])
        freqs_rx = np.fft.fftfreq(len(rx1_fd), d=time_vec_rx[1] - time_vec_rx[0])
        plt.figure()
        plt.plot(freqs_tx / 1e6, 20 * np.log10(np.abs(tx1_fd / len(tx1_fd))))
        plt.plot(freqs_tx / 1e6, 20 * np.log10(np.abs(tx2_fd / len(tx2_fd))))
        plt.plot(freqs_rx / 1e6, 20 * np.log10(np.abs(rx1_fd / len(rx1_fd))))
        plt.plot(freqs_rx / 1e6, 20 * np.log10(np.abs(rx2_fd / len(rx2_fd))))
        plt.xlabel("Frequency [MHz]")
        plt.ylabel("Magnitude [dB]")
        plt.legend(["Tx1", "Tx2", "Rx1", "Rx2"])
        plt.ylim(-100, -30)
        plt.grid(True)
        plt.show()

    if args["verbose"]:
        print_statistics(rx_stats, tx_stats)

    return


def main():
    success = False

    args: dict[str, Any] = {
        "center_freq": 0.5e9,
        "sampling_rate": 25e6,  # samples per second
        "channel_list": [0, 1],  # [0] or [0,1], applies to both tx and rx
        "chirp_bw": 8e6,
        "chirp_ampl": 0.3,  # float between 0 and 1
        "chirp_duration": 1.025e-5,
        "tx_gain": 60,  # [dB]
        "rx_samples": 50000,
        "rx_antenna": "RX2",  # "RX2" or "TX/RX"
        "rx_gain": 45,  # [dB]
        "rx_auto_gain": False,
        "output_filename": "",  # "Monostatic_newPCBAnt_Reflection4m_25MSps_3GHz",  # set to empty string to not save data to file
        "plot_data": True,
        "verbose": False,
    }

    args.update({"tx_rate": args["sampling_rate"], "rx_rate": args["sampling_rate"]})
    verbose = args["verbose"]

    # TODO: implement arg checking, command-line args
    # args = argparse()
    # success, err_msg = validate_args(args)
    # if not success:
    #     logging.error(err_msg)

    usrp = usrp_setup(args, logger, verbose)
    num_channels = len(args["channel_list"])

    rx_buffer = np.zeros(
        [num_channels, args["rx_samples"]], dtype=np.complex64
    )
    tx_buffer = dc_chirp(
        args["chirp_ampl"],
        args["chirp_bw"],
        args["sampling_rate"],
        args["chirp_duration"],
        pad=True,
    )
    if len(tx_buffer.shape) == 1:
        tx_buffer = tx_buffer.reshape(1, tx_buffer.size)
    if num_channels > 1:
        tx_buffer = np.tile(tx_buffer, (num_channels,1))
    print(tx_buffer.shape)
    tx_dat, rx_dat, tx_stats, rx_stats = start_threads(usrp, tx_buffer, rx_buffer)
    generate_output(args, tx_dat, rx_dat, tx_stats, rx_stats)
    success = True

    return success


if __name__ == "__main__":
    RX_DELAY = 0.049  # offset delay between transmitting and receiving @TODO: put this into args?
    TX_DELAY = 0.05

    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    logger.addHandler(console)
    formatter = LogFormatter(
        fmt="[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s"
    )
    console.setFormatter(formatter)

    sys.exit(not main())
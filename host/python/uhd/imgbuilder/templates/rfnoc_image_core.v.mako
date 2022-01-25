<%
    import datetime
    [protover_major, protover_minor, *_] = config.rfnoc_version.split('.')
%>//
// Copyright ${datetime.datetime.now().year} ${config.copyright}
//
// ${config.license}
//
// Module: rfnoc_image_core (for ${config.device.type})
//
// Description:
//
//   The RFNoC Image Core contains the Verilog description of the RFNoC design
//   to be loaded onto the FPGA.
//
//   This file was automatically generated by the RFNoC image builder tool.
//   Re-running that tool will overwrite this file!
//
// File generated on: ${datetime.datetime.now().isoformat()}
% if source:
// Source: ${source}
% endif
% if source_hash:
// Source SHA256: ${source_hash}
% endif
//

`default_nettype none


module rfnoc_image_core #(
  parameter        CHDR_W     = ${config.chdr_width},
  parameter        MTU        = 10,
  parameter [15:0] PROTOVER   = {8'd${protover_major}, 8'd${protover_minor}},
  parameter        RADIO_NIPC = 1
) (
  // Clocks
  input  wire         chdr_aclk,
  input  wire         ctrl_aclk,
  input  wire         core_arst,
%for clock in config.device.clocks:
  input  wire         ${clock["name"]}_clk,
%endfor
  // Basic
  input  wire [  15:0] device_id,

<%include file="/modules/device_io_ports.v.mako" args="io_ports=config.device.io_ports"/>\
<%include file="/modules/device_transport.v.mako" args="transports=config.device.transports"/>\
);

  localparam EDGE_TBL_FILE = `"`RFNOC_EDGE_TBL_FILE`";

  wire rfnoc_chdr_clk, rfnoc_chdr_rst;
  wire rfnoc_ctrl_clk, rfnoc_ctrl_rst;


  //---------------------------------------------------------------------------
  // CHDR Crossbar
  //---------------------------------------------------------------------------

<%include file="/modules/sep_xb_wires.v.mako" args="seps=config.stream_endpoints"/>\

  chdr_crossbar_nxn #(
    .CHDR_W         (CHDR_W),
    .NPORTS         (${len(config.stream_endpoints) + len(config.device.transports)}),
    .DEFAULT_PORT   (0),
    .MTU            (MTU),
    .ROUTE_TBL_SIZE (6),
    .MUX_ALLOC      ("ROUND-ROBIN"),
    .OPTIMIZE       ("AREA"),
    .NPORTS_MGMT    (${len(config.device.transports)}),
    .EXT_RTCFG_PORT (0),
    .PROTOVER       (PROTOVER)
  ) chdr_xb_i (
    .clk            (rfnoc_chdr_clk),
    .reset          (rfnoc_chdr_rst),
    .device_id      (device_id),
<%include file="/modules/chdr_xb_sep_transport.v.mako" args="seps=config.stream_endpoints, transports=config.device.transports"/>\
    .ext_rtcfg_stb  (1'h0),
    .ext_rtcfg_addr (16'h0),
    .ext_rtcfg_data (32'h0),
    .ext_rtcfg_ack  ()
  );


  //---------------------------------------------------------------------------
  // Stream Endpoints
  //---------------------------------------------------------------------------

<%include file="/modules/stream_endpoints.v.mako" args="seps=config.stream_endpoints"/>\
<%
    from collections import OrderedDict
    ctrl_seps = OrderedDict((k, v) for k, v in config.stream_endpoints.items() if v.get('ctrl'))
%>
  //---------------------------------------------------------------------------
  // Control Crossbar
  //---------------------------------------------------------------------------

  wire [31:0] m_core_ctrl_tdata,  s_core_ctrl_tdata;
  wire        m_core_ctrl_tlast,  s_core_ctrl_tlast;
  wire        m_core_ctrl_tvalid, s_core_ctrl_tvalid;
  wire        m_core_ctrl_tready, s_core_ctrl_tready;
<%include file="/modules/ctrl_crossbar.v.mako" args="seps=ctrl_seps, blocks=config.noc_blocks"/>\


  //---------------------------------------------------------------------------
  // RFNoC Core Kernel
  //---------------------------------------------------------------------------

  wire [(512*${len(config.noc_blocks)})-1:0] rfnoc_core_config, rfnoc_core_status;

  rfnoc_core_kernel #(
    .PROTOVER            (PROTOVER),
    .DEVICE_TYPE         (16'h${config.device.type_id}),
    .DEVICE_FAMILY       ("${config.device.family}"),
    .SAFE_START_CLKS     (0),
    .NUM_BLOCKS          (${len(config.noc_blocks)}),
    .NUM_STREAM_ENDPOINTS(${len(config.stream_endpoints)}),
    .NUM_ENDPOINTS_CTRL  (${len(ctrl_seps)}),
    .NUM_TRANSPORTS      (${len(config.device.transports)}),
    .NUM_EDGES           (${len(config.block_con)}),
    .CHDR_XBAR_PRESENT   (1),
    .EDGE_TBL_FILE       (EDGE_TBL_FILE)
  ) core_kernel_i (
    .chdr_aclk          (chdr_aclk),
    .chdr_aclk_locked   (1'b1),
    .ctrl_aclk          (ctrl_aclk),
    .ctrl_aclk_locked   (1'b1),
    .core_arst          (core_arst),
    .core_chdr_clk      (rfnoc_chdr_clk),
    .core_chdr_rst      (rfnoc_chdr_rst),
    .core_ctrl_clk      (rfnoc_ctrl_clk),
    .core_ctrl_rst      (rfnoc_ctrl_rst),
    .s_axis_ctrl_tdata  (s_core_ctrl_tdata),
    .s_axis_ctrl_tlast  (s_core_ctrl_tlast),
    .s_axis_ctrl_tvalid (s_core_ctrl_tvalid),
    .s_axis_ctrl_tready (s_core_ctrl_tready),
    .m_axis_ctrl_tdata  (m_core_ctrl_tdata),
    .m_axis_ctrl_tlast  (m_core_ctrl_tlast),
    .m_axis_ctrl_tvalid (m_core_ctrl_tvalid),
    .m_axis_ctrl_tready (m_core_ctrl_tready),
    .device_id          (device_id),
    .rfnoc_core_config  (rfnoc_core_config),
    .rfnoc_core_status  (rfnoc_core_status)
  );


  //---------------------------------------------------------------------------
  // Blocks
  //---------------------------------------------------------------------------
%for i, name in enumerate(config.noc_blocks):
<%include file="/modules/rfnoc_block.v.mako" args="block_id=i + len(ctrl_seps) + 1, block_number=i, block_name=name, block=config.blocks[config.noc_blocks[name]['block_desc']], block_params=config.noc_blocks[name]['parameters'], block_ports=config.block_ports"/>\
%endfor

  //---------------------------------------------------------------------------
  // Static Router
  //---------------------------------------------------------------------------

<%include file="/modules/static_router.v.mako" args="connections=config.block_con"/>\

  //---------------------------------------------------------------------------
  // Unused Ports
  //---------------------------------------------------------------------------

<%include file="/modules/drive_unused_ports.v.mako" args="connections=config.block_con, block_ports=config.block_ports"/>\


  //---------------------------------------------------------------------------
  // Clock Domains
  //---------------------------------------------------------------------------

<%include file="/modules/connect_clk_domains.v.mako" args="connections=config.clk_domain_con, clocks=config.clocks"/>\


  //---------------------------------------------------------------------------
  // IO Port Connection
  //---------------------------------------------------------------------------

  // Master/Slave Connections:
<%include file="/modules/connect_io_ports.v.mako" args="connections=config.io_port_con_ms, io_ports=config.io_ports, names=('master', 'slave')"/>\
  // Broadcaster/Listener Connections:
<%include file="/modules/connect_io_ports.v.mako" args="connections=config.io_port_con_bl, io_ports=config.io_ports, names=('broadcaster', 'listener')"/>\
endmodule


`default_nettype wire

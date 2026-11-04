interface stream_if (input logic clk);
  logic        valid, ready, last;
  logic [63:0] data;
  clocking drv_cb @(posedge clk); output valid, data, last; input ready; endclocking
  clocking mon_cb @(posedge clk); input valid, data, last, ready; endclocking
  modport drv (clocking drv_cb);
  modport mon (clocking mon_cb);
endinterface

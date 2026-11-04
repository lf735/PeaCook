interface apb_if (input logic clk);
  logic        psel, penable, pwrite, pready;
  logic [31:0] paddr, pwdata, prdata;
  clocking drv_cb @(posedge clk); output psel, penable, pwrite, paddr, pwdata; input pready, prdata; endclocking
  clocking mon_cb @(posedge clk); input psel, penable, pwrite, paddr, pwdata, pready, prdata; endclocking
  modport drv (clocking drv_cb);
  modport mon (clocking mon_cb);
endinterface

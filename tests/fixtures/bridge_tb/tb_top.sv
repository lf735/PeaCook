module tb_top;
  import uvm_pkg::*;
  import bridge_tests_pkg::*;

  logic clk = 0;
  always #5 clk = ~clk;

  apb_if    apb_vif  (clk);
  stream_if in_vif   (clk);
  stream_if out_vif0 (clk);
  stream_if out_vif1 (clk);
  stream_if out_vif2 (clk);
  stream_if out_vif3 (clk);

  bridge_dut dut (.clk(clk), .apb(apb_vif), .in(in_vif), .out0(out_vif0), .out1(out_vif1));

  initial begin
    uvm_config_db#(virtual apb_if)::set(null, "uvm_test_top.env.apb_agt*", "vif", apb_vif);
    uvm_config_db#(virtual stream_if)::set(null, "uvm_test_top.env.in_agt*", "vif", in_vif);
    uvm_config_db#(virtual stream_if)::set(null, "uvm_test_top.env.out_agt_0*", "vif", out_vif0);
    uvm_config_db#(virtual stream_if)::set(null, "uvm_test_top.env.out_agt_1*", "vif", out_vif1);
    uvm_config_db#(virtual stream_if)::set(null, "uvm_test_top.env.out_agt_2*", "vif", out_vif2);
    uvm_config_db#(virtual stream_if)::set(null, "uvm_test_top.env.out_agt_3*", "vif", out_vif3);
    // Volontairement jamais lu : sert à tester la détection de config_db orphelin
    uvm_config_db#(int)::set(null, "uvm_test_top.env", "debug_level", 1);
    run_test();
  end
endmodule

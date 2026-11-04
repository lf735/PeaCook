package apb_pkg;
  import uvm_pkg::*;
  `include "uvm_macros.svh"

  `include "apb_item.svh"
  `include "apb_cfg.svh"
  `include "apb_driver.svh"
  `include "apb_monitor.svh"
  typedef uvm_sequencer #(apb_item) apb_sequencer;
  `include "apb_agent.svh"
  `include "apb_seqs.svh"
endpackage

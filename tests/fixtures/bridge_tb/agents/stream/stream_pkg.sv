package stream_pkg;
  import uvm_pkg::*;
  `include "uvm_macros.svh"

  `include "stream_item.svh"
  `include "stream_components.svh"
  typedef uvm_sequencer #(stream_item) stream_sequencer;
  `include "stream_agent.svh"
  `include "stream_seqs.svh"
endpackage

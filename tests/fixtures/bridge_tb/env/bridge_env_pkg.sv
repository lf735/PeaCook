package bridge_env_pkg;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  import apb_pkg::*;
  import stream_pkg::*;

  `uvm_analysis_imp_decl(_exp)
  `uvm_analysis_imp_decl(_act)

  `include "bridge_env_cfg.svh"
  `include "bridge_vseqr.svh"
  `include "bridge_ref_model.svh"
  `include "bridge_scoreboard.svh"
  `include "bridge_coverage.svh"
  `include "bridge_env.svh"
  `include "bridge_vseqs.svh"
endpackage

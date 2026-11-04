class bridge_env extends uvm_env;
  `uvm_component_utils(bridge_env)
  bridge_env_cfg       cfg;
  apb_agent            apb_agt;
  stream_agent         in_agt;
  stream_agent         out_agts[];
  bridge_ref_model     ref_model;
  bridge_scoreboard    sb;
  bridge_coverage      cov;
  bridge_vseqr         vseqr;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(bridge_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("NOCFG", "bridge_env_cfg not set")

    apb_agt = apb_agent::type_id::create("apb_agt", this);
    in_agt  = stream_agent::type_id::create("in_agt", this);
    uvm_config_db#(uvm_active_passive_enum)::set(this, "in_agt", "is_active", UVM_ACTIVE);

    out_agts = new[cfg.num_out];
    foreach (out_agts[i]) begin
      out_agts[i] = stream_agent::type_id::create($sformatf("out_agt_%0d", i), this);
      uvm_config_db#(uvm_active_passive_enum)::set(this, $sformatf("out_agt_%0d", i), "is_active", UVM_PASSIVE);
    end

    if (cfg.has_ref_model)
      ref_model = bridge_ref_model::type_id::create("ref_model", this);
    sb    = bridge_scoreboard::type_id::create("sb", this);
    if (cfg.enable_cov)
      cov = bridge_coverage::type_id::create("cov", this);
    vseqr = bridge_vseqr::type_id::create("vseqr", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    if (cfg.has_ref_model) begin
      in_agt.mon.ap.connect(ref_model.in_fifo.analysis_export);
      ref_model.ap.connect(sb.exp_imp);
    end
    foreach (out_agts[i])
      out_agts[i].ap.connect(sb.act_imp);
    if (cfg.enable_cov)
      apb_agt.ap.connect(cov.analysis_export);
    vseqr.apb_sqr = apb_agt.sqr;
    vseqr.in_sqr  = in_agt.sqr;
  endfunction
endclass

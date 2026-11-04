class bridge_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(bridge_scoreboard)
  uvm_analysis_imp_exp #(stream_item, bridge_scoreboard) exp_imp;
  uvm_analysis_imp_act #(stream_item, bridge_scoreboard) act_imp;
  stream_item exp_q[$];
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    exp_imp = new("exp_imp", this);
    act_imp = new("act_imp", this);
  endfunction
  function void write_exp(stream_item t);
    exp_q.push_back(t);
  endfunction
  function void write_act(stream_item t);
    stream_item e;
    if (exp_q.size() == 0) `uvm_error("SB", "unexpected item")
    else begin
      e = exp_q.pop_front();
      if (!e.compare(t)) `uvm_error("SB", "mismatch")
    end
  endfunction
endclass

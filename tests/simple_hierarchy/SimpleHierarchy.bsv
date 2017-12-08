interface MyFIFO;
    method Action enq(Bit#(32) x);
    method Bit#(32) first();
    method Action deq();
endinterface

(* synthesize *)
module mkMyFIFO#(parameter Bit#(32) min_delay, Bit#(32) current_cycle)(MyFIFO);
    Reg#(Bit#(32)) deq_time <- mkReg(0);
    Reg#(Maybe#(Bit#(32))) in_data <- mkReg(tagged Invalid);
    Reg#(Maybe#(Bit#(32))) out_data <- mkReg(tagged Invalid);

    rule propagate(in_data matches tagged Valid .x &&& !isValid(out_data) &&& (current_cycle > deq_time));
        $display("[BSV] propagate for MyFIFO with min_delay = %0d", min_delay);
        out_data <= tagged Valid x;
        in_data <= tagged Invalid;
    endrule

    method Action enq(Bit#(32) x) if (!isValid(in_data));
        in_data <= tagged Valid x;
        deq_time <= current_cycle + min_delay;
    endmethod
    method Bit#(32) first() if (out_data matches tagged Valid .x);
        return x;
    endmethod
    method Action deq() if (isValid(out_data));
        out_data <= tagged Invalid;
    endmethod
endmodule

interface SimpleHierarchy;
    method Action enq_both(Bit#(32) fast, Bit#(32) slow);
endinterface

(* synthesize *)
module mkSimpleHierarchy(SimpleHierarchy);
    Reg#(Bit#(32)) cycle <- mkReg(0);
    MyFIFO fast_fifo <- mkMyFIFO(1, cycle);
    MyFIFO slow_fifo <- mkMyFIFO(10, cycle);

    rule increment_cycle;
        cycle <= cycle + 1;
        $display("[BSV] cycle = %0d", cycle + 1);
    endrule

    rule enq_cycle_to_fast_fifo;
        fast_fifo.enq(cycle);
        $display("[BSV] fast_fifo.enq(%0d)", cycle);
    endrule
    rule deq_fast_fifo_and_print;
        let x = fast_fifo.first();
        fast_fifo.deq;
        $display("[BSV] fast_fifo.deq() -> %0d", x);
    endrule

    rule enq_cycle_to_slow_fifo;
        slow_fifo.enq(cycle);
        $display("[BSV] slow_fifo.enq(%0d)", cycle);
    endrule
    rule deq_slow_fifo_and_print;
        let x = slow_fifo.first();
        slow_fifo.deq;
        $display("[BSV] slow_fifo.deq() -> %0d", x);
    endrule

    method Action enq_both(Bit#(32) fast, Bit#(32) slow);
        fast_fifo.enq(fast);
        slow_fifo.enq(slow);
    endmethod
endmodule

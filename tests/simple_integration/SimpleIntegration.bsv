module mkSimpleIntegration(Empty);
    Reg#(Bit#(8)) a <- mkReg(0);
    Reg#(Bit#(8)) b <- mkReg(1);
    Reg#(Bit#(8)) c <- mkReg(2);
    Reg#(Bit#(8)) d <- mkReg(3);
    Wire#(Bool) bypass_wire <- mkDWire(False);

    rule always_ready_and_enabled;
        $display("always ready and enabled\n");
        a <= a + 1;
    endrule

    rule same_guard_1(a[0] == 0);
        b <= b + 1;
        $display("same guard 1\n");
    endrule

    rule same_guard_2(a[0] == 0);
        c <= c + 1;
        $display("same guard 2\n");
    endrule

    rule bypassing_src(a[1] == 0);
        bypass_wire <= True;
        $display("bypassing src\n");
    endrule

    rule bypassing_dst(bypass_wire);
        $display("bypassing dst\n");
        d <= d + 1;
    endrule
endmodule

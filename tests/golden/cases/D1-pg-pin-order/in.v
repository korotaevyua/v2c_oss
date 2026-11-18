// D1: every instance carries its own power, ground and well pins, written in
// the order P&R tools use (outputs first, VSS before VDD); each must land in
// the library's position. The buffer takes its wells from separate body-bias
// ports, so a swapped VNW/VDD or VPW/VSS shows up as a wrong net; the other
// cells tie their wells to the rails, as most post-route netlists do.
// Also: a tie-low cell is an ordinary cell (F2), and the unused input SE stays
// a .SUBCKT pin.
module cg (
        CK,
        E,
        SE,
        ECK,
        VDD,
        VSS,
        VNWB,
        VPWB);
   input CK;
   input E;
   input SE;
   output ECK;
   inout VDD;
   inout VSS;
   inout VNWB;
   inout VPWB;

   // Internal wires
   wire e_buf;
   wire tie_lo;

   // Module instantiations
   BUFX u_buf (
        .Z(e_buf),
        .A(E),
        .VSS(VSS),
        .VPW(VPWB),
        .VNW(VNWB),
        .VDD(VDD));
   TIELO u_tie (
        .Z(tie_lo),
        .VSS(VSS),
        .VPW(VSS),
        .VNW(VDD),
        .VDD(VDD));
   CKGATE u_cg (
        .TE(tie_lo),
        .Q(ECK),
        .E(e_buf),
        .CK(CK),
        .VSS(VSS),
        .VPW(VSS),
        .VNW(VDD),
        .VDD(VDD));
endmodule

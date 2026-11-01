// C3: buses are bit-blasted. A bus port becomes one pin per bit, a bit select
// picks one bit, and a whole bus on a macro's bus pin covers all of its bits.
module top (mode, en, q, VDD, VSS);
   input [1:0] mode;
   input en;
   output [1:0] q;
   inout VDD;
   inout VSS;
   wire [1:0] mode_n;

   INV u_inv0 (.A(mode[0]), .Y(mode_n[0]), .VDD(VDD), .VSS(VSS));
   INV u_inv1 (.A(mode[1]), .Y(mode_n[1]), .VDD(VDD), .VSS(VSS));
   MODECTL u_ctl (.EN(en), .SEL(mode_n), .Q(q), .VDD(VDD), .VSS(VSS));
endmodule

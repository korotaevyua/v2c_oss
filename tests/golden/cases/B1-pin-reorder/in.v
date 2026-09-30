// B1: named connections written in orders that differ from the library
// .SUBCKT pin order. The CDL follows the library, whatever the source says.
module top (d, en, clk, rst_n, q, VDD, VSS);
  input d, en, clk, rst_n;
  output q;
  inout VDD, VSS;
  wire dn, q_int, q_bar;

  // alphabetical, as some tools write it
  AOI21 u_mux (.A1(d), .A2(en), .B(q_int), .VDD(VDD), .VSS(VSS), .Y(dn));
  // outputs and supplies first
  DFFR u_reg (.QN(q_bar), .Q(q_int), .VSS(VSS), .VDD(VDD), .RN(rst_n), .CK(clk),
              .D(dn));
  // the exact reverse of the library order
  INV u_out (.VSS(VSS), .VDD(VDD), .Y(q), .A(q_bar));
endmodule

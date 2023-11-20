Cerinte facute: 1 2 3

# 1. Tabela de comutare

S-a implementat pseudocodul din enuntul temei, se trece interfata de pe care a venit pachetul in tabela de comutare, se verifica daca pachetul este unicast, daca destinatia se afla in tabela se trimite acolo, daca nu, se face flood.

# 2. VLAN

Pentru implementarea VLAN-urilor, pentru fiecare pachet primit se verifica daca este venit de pe interfata access sau trunk, se creeaza 2 pachete (unul cu 802.1q header, altul fara) si se trimite cel de care este nevoie daca urmeaza sa fie forwarded pe un port trunk sau access.

De asemenea, se tine cont ca locul unde se trimite sa fie in acelasi VLAN ca statia care a trimis pachetul.

# 3. STP

Pentru STP a fost implementata functia `send_bdpu_every_sec()` care verifica daca switch-ul este root bridge si trimite mai departe pe toate interfetele trunk un pachet BDPU.

In loop-ul principal al switch-ului, in caz ca se primeste un pachet BDPU, se procedeaza conform indicatiilor din enunt. Pentru interfete a fost implementata o clasa ajutatoare care sa encapsuleze datele si starea in care se afla fiecare (in cazul acesta, LISTENING sau BLOCKED).
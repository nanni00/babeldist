#!/bin/bash
ssh-add ~/.ssh/id_rsababel
ssh -L 7780:localhost:7780 -L 7790:localhost:7790 ssh-guest@trafair-srv.ing.unimo.it

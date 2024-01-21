here is the output of the data of 1 symbol:

{"ranges": [[1.7909, 1.7640365], [1.7927499999999998, 1.7658587499999998], [1.79285, 1.76595725]], "orders_per_range": [19, 1, 9]}

as you can see the ranges still overlap, I would expect the following:

- Range 1from opening position (first position we started for the symbol) to 1,5% below that
- Range 2 from previous end range to again 1,5% below that
- etc..

 so for example:

- Range 1: 100 - 98,5 (1,5% diff)
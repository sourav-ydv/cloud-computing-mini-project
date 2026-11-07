# Subnet allocation for 10.20.0.0/16

Allocated largest requirement first, each subnet starting right after the previous one.

usable hosts = 2^(32-prefix) - 2

| Subnet | Hosts needed | Prefix found | Network | Broadcast | Usable range | Usable hosts |
|---|---|---|---|---|---|---|
| app | 1000 | /22 (2^10-2=1022 >= 1000) | 10.20.0.0 | 10.20.3.255 | 10.20.0.1 - 10.20.3.254 | 1022 |
| public | 250 | /24 (2^8-2=254 >= 250) | 10.20.4.0 | 10.20.4.255 | 10.20.4.1 - 10.20.4.254 | 254 |
| data | 100 | /25 (2^7-2=126 >= 100) | 10.20.5.0 | 10.20.5.127 | 10.20.5.1 - 10.20.5.126 | 126 |
| management | 20 | /27 (2^5-2=30 >= 20) | 10.20.5.128 | 10.20.5.159 | 10.20.5.129 - 10.20.5.158 | 30 |

Working:

- app needs 1000 usable hosts. /23 gives 2^9-2=510, too small. /22 gives 2^10-2=1022, fits. Block: 10.20.0.0/22, occupies 10.20.0.0 - 10.20.3.255.
- Next free address: 10.20.4.0. public needs 250. /25 gives 126, too small. /24 gives 254, fits. Block: 10.20.4.0/24, occupies 10.20.4.0 - 10.20.4.255.
- Next free address: 10.20.5.0. data needs 100. /26 gives 62, too small. /25 gives 126, fits. Block: 10.20.5.0/25, occupies 10.20.5.0 - 10.20.5.127.
- Next free address: 10.20.5.128. management needs 20. /28 gives 14, too small. /27 gives 30, fits. Block: 10.20.5.128/27, occupies 10.20.5.128 - 10.20.5.159.

Database of Pokémon products. View it [here](https://fatalmistake02.github.io/pokemon-products/) or download the products.json file.

For easily creating products run the server.
You will need nodejs. |
First install express and cors: ```npm install express cors``` |
To start the server run: ```node server.js```

For autofill to work you must type the name correctly. They are usually correct on TCGplayer. Note that it will only work for certain products. All are added to autofill.json and sets are in sets.json. |
Type will be auto-filled when possible. |
Descriptions will be auto-filled when possible. Some will need changing. |
Packs will be auto-filled when possible and will only need the set id changed if the set isn't found. |
Image url will be auto-filled from the tcgplayer id.

Sets need to be added to sets.json for the autofill. | 
Run set updater ```python update_sets.py``` | 
You will need requests ```pip install requests```

To link each product's TCGplayer ID to its Cardmarket and CardTrader IDs, run:

```sh
python link_marketplace_ids.py
```

This uses the [TCG Tracking API](https://openapi.tcgtracking.com/) and updates
`products.json`. Products that already have both marketplace IDs are skipped.
To link products from only one set, pass its set ID:

```sh
python link_marketplace_ids.py --set sv01
```

You can use this data in any way you like for any purpose

Pokémon and Pokémon character names, card images, and related assets are © Nintendo, Creatures, and GAME FREAK.

Pokémon TCG is a registered trademark of The Pokémon Company International.

This database is not affiliated with, endorsed by, sponsored by, or associated with Nintendo, Creatures, GAME FREAK, or The Pokémon Company.

All Pokémon-related content belongs to its respective owners.

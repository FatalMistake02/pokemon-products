const express = require('express');
const fs = require('fs');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 3000;
const JSON_FILE = 'products.json';

app.use(cors());
app.use(express.json());
app.use(express.static('.'));

function slugifyProductName(name) {
    return String(name || "")
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function generateUniqueProductId(products, name, currentId = null) {
    const baseId = slugifyProductName(name);
    if (!baseId) return currentId || null;

    const existingIds = new Set(
        products
            .filter(product => product.id !== currentId)
            .map(product => product.id)
            .filter(Boolean)
    );
    if (!existingIds.has(baseId)) return baseId;

    let suffix = 2;
    while (existingIds.has(`${baseId}-${suffix}`)) {
        suffix += 1;
    }
    return `${baseId}-${suffix}`;
}

app.post('/update-products', (req, res) => {
    const { original_id: originalId, ...updatedProduct } = req.body;

    fs.readFile(JSON_FILE, 'utf8', (err, data) => {
        if (err) return res.status(500).send("Error reading file");

        let products = JSON.parse(data || "[]");
        const currentId = originalId || null;
        updatedProduct.id = generateUniqueProductId(products, updatedProduct.name, currentId);

        if (!updatedProduct.id) {
            return res.status(400).send("Product name is required to generate an ID");
        }

        const index = currentId
            ? products.findIndex(p => p.id === currentId)
            : products.findIndex(p => p.id === updatedProduct.id);

        if (index !== -1) {
            products[index] = updatedProduct;
            console.log(`Updating existing product: ${updatedProduct.id}`);
        } else {
            products.push(updatedProduct);
            console.log(`Adding new product: ${updatedProduct.id}`);
        }

        fs.writeFile(JSON_FILE, JSON.stringify(products, null, 2), (err) => {
            if (err) return res.status(500).send("Error writing file");
            res.send({ message: "Success" });
        });
    });
});

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});

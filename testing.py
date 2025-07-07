import camelot

# Use the correct path to your PDF file
tables = camelot.read_pdf("data/Nibav_FAQ 1.pdf", pages="1")
print(tables)
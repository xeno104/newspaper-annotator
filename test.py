def deobfuscate_string(encoded_str):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/"
    reversed_alphabet = alphabet[::-1]

    decoded_str = ""
    for char in encoded_str:
        index = reversed_alphabet.find(char)
        if index != -1:
            decoded_str += alphabet[index]
        else:
            decoded_str += char

    return decoded_str

def parse_newspaper_data(encoded_str):
    """Decodes the string and splits it into the base URL and page paths"""
    decoded_str = deobfuscate_string(encoded_str)

    # Split the string just like JS: parseDeobfuscatedData(e.split("q!"))
    parts = decoded_str.split("q!")

    if len(parts) >= 3:
        file_type = parts[0]
        base_url = parts[1]

        # In their JS, they split the suffix by 'm%' to get individual pages
        pages_string = parts[2]
        page_paths = [p.strip() for p in pages_string.split("m%") if p.strip()]

        return {
            "type": file_type,
            "base_url": base_url,
            "pages": page_paths
        }
    return None

# --- Example Test ---
# Let's test it on a snippet of the AajTak payload you shared earlier:
test_payload = "V75U!3RRVS:aa2Y/46.Y6V/V6T.X/P93/T/RR2Y6S.8WYa6V/V6T2Y/46SaaibkfikieaU!ibkfikie-Y7-76-j.V75Y%ibkfikie-Y7-76-i.V75Y%ibkfikie-Y7-76-h.V75Y%ibkfikie-Y7-76-g.V75Y%ibkfikie-Y7-76-f.V75Y%ibkfikie-Y7-76-e.V75Y%ibkfikie-Y7-76-d.V75Y%ibkfikie-Y7-76-c.V75Y%ibkfikie-Y7-76-b.V75Y%ibkfikie-Y7-76-jk.V75Y%ibkfikie-Y7-76-jj.V75Y%ibkfikie-Y7-76-ji.V75Y%ibkfikie-Y7-76-jh.V75Y%ibkfikie-Y7-76-jg.V75Y%ibkfikie-Y7-76-jf.V75Y%ibkfikie-Y7-76-je.V75"
parsed_data = parse_newspaper_data(test_payload)
print(f"Base URL: {parsed_data['base_url']}")
print(f"Pages: {parsed_data['pages']}")

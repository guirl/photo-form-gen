# stars.py

def stars(input_data):
    rating = float(input_data['rating'])
    chars = {
        "empty": ":white_heart:",
        "half":  ":pink_heart:",
        "full":  ":heart:"
    }
    rating_chars = []

    for star in range(1, 6):
        print(f"star: {star}, rating: {rating}")
        if rating >= star:
            # full
            rating_chars.append(chars['full'])
        elif rating >= star - 0.5:
            # half
            rating_chars.append(chars['half'])
        else:
            # empty
            rating_chars.append(chars['empty'])

    rating_formatted = "".join(rating_chars)
    return rating_formatted



if __name__ == "__main__":
    for toten in range(0, 21):
        rating = toten / 4
        input = {"rating": str(rating)}
        star_rating = stars(input)
                             
        print(f"rating: {rating}, stars: {star_rating}")
   
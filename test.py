message = "so $450 message long"
word = '$450'
# get just the number
amount = message.split()[message.split().index(word) - 1]
amount = ''.join([i for i in amount if i.isnumeric()])
print(amount)
amount = float(amount)
print(amount)
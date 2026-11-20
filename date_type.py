x = 500
y = "500" #오백

print(type(x))
print(type(y))

if y == 500:
    print("변수y는 숫자 자료형입니다.")
else:
    print("변수y는 숫자 자료형이 아닙니다.")

print(500+500)
print(x+x)
print(x+int(y))

input_text = input("입력하세요 : ")
print(f"입력받은 값은 {input_text}입니다.")
print(f"입력받은 값의 자료형은 {type(input_text)}입니다.")
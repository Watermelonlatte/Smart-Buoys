import time
import requests

tinyIoT_url = "http://127.0.0.1:3000/TinyIoT/WaveMonitoringApp/?rcn=4"


def monitor_wave_data():
    headers = {
        "X-M2M-Origin": "CAdmin",
        "Content-Type": "application/json",
        "X-M2M-RVI": "3",
    }

    response = requests.get(tinyIoT_url, headers=headers)

    if response.status_code == 200:
        data = response.json()

        if "m2m:ae" in data and "m2m:cnt" in data["m2m:ae"]:
            cnt_list = data["m2m:ae"]["m2m:cnt"]
            dangerous_count = 0
            caution_count = 0

            for cnt in cnt_list:
                if "m2m:cin" in cnt:
                    cin_list = cnt["m2m:cin"]
                    for cin in cin_list:
                        content = cin["con"]
                        wave_condition = content.get("wave_condition", "")
                        print(f"- {wave_condition}")

                        if wave_condition == "Dangerous":
                            dangerous_count += 1
                        elif wave_condition == "Caution":
                            caution_count += 1
                else:
                    print("m2m:cin key is missing in the cnt object.")

            if dangerous_count > 3:
                print(f"경고: {dangerous_count}개의 위험 경보가 감지되었습니다!")
            elif caution_count > 3:
                print(f"주의: {caution_count}개의 주의 경보가 감지되었습니다!")
            else:
                print("현재 파도 상태는 안전합니다.")

            # print("10초 세트 끝")
        else:
            print("m2m:ae or m2m:cnt key is missing in the response.")
    else:
        print
        (
            f"Failed to retrieve CNT data. Status code: {
                response.status_code}, Response: {response.text}"
        )


while True:
    monitor_wave_data()
    time.sleep(10)

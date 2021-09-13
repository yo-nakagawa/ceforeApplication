import fcntl
import netifaces
import os
import socket
import struct
import subprocess
import sys
import threading
import tkinter
from time import sleep

import cefpyco
import psutil
from scapy.all import *

class Member:
    myname = ""
    groupname = ""

class Publisher(Member):
    seq = 0
    generated_massage_repository = dict()
    interest_pending_repository = []

    def generate(self):
        message_name = "ccn:"+ super().myname +"/"+str(Publisher.seq)#グローバル変数ではなく、クラス変数を参照した
        message = Gui.get_message()
        if message == "": return    #メッセージ指定していないときは、生成しない
        Publisher.seq += 1
        Publisher.generated_massage_repository[message_name] = message 
        Gui.generate_message_window_update()
        #要求中のメッセージが生成された場合にメッセージを送信
        print(Publisher.interest_pending_repository)
        if message_name in Publisher.interest_pending_repository:
            with cefpyco.create_handle() as handle:
                handle.send_data(message_name,Publisher.generated_massage_repository[message_name],0)

    def sending_data(name, handle):
        handle.send_data(name,Publisher.generated_massage_repository[name],0)
    
    def pending_interest(name):
        Publisher.interest_pending_repository.append(name)


class Subscriber(Member):
    received_massage_repository = dict()
    sended_interest_repository = dict()
    global timeout_list

    def calculate_sequence_num(a,num):
        num += 1
        return num

    def create_packet_name(self, name):
        name_split = name.split('/') 
        sequence_num = int(name_split[2])
        sequence_num = self.calculate_sequence_num(sequence_num)
        name = name_split[0] + "/"+ name_split[1] + "/" + str(sequence_num)
        return name

    def sending_interest(self):
        count = 0
        with cefpyco.create_handle() as handle:
            #受信したいInterestの名前（prefixだけでもok）を指定    
            handle.register("ccn:"+super().myname)
            #パケット受信した際の処理 
            while True:
                if len(fib_list) > 0:
                    count += 1
                    #メンバ全員にシーケンス0のIntetest送信(初期処理) 
                    if count == 1:
                        for membername in member_list:  
                            packetname = "ccn:"+ membername + "/-1"
                            packetname = self.create_packet_name(packetname)
                            handle.send_interest(packetname,0)
                            #各メンバに対する要求メッセージのシーケンス番号を記録
                            Subscriber.sended_interest_repository[membername] = 0

                    info = handle.receive()
                    mem = ""
                    #print(info.name)
                    if info.is_succeeded:
                        #Interestを受信した場合
                        if info.is_interest:
                            if info.name in Publisher.generated_massage_repository.keys():
                                Publisher.sending_data(info.name, handle)
                            else:
                                if info.name.startswith(super().myname): #自身宛かつ未発行のメッセージに対するInterestの場合
                                    Publisher.pending_interest(info.name)
                                else:   #グループ内別メンバ宛へのメッセージに対するInterestの場合
                                    if info.name in Subscriber.received_massage_repository.keys():
                                        #キャッシュされている場合
                                        Publisher.sending_data(info.name, handle)
                                    else:
                                        handle.send_interest(info.name,0)

                        #Dataを受信した場合
                        else:
                            mem = info.name[4:8]
                            seq = info.name[9]
                            if not (mem in Subscriber.sended_interest_repository.keys() \
                            and seq in str(Subscriber.sended_interest_repository[mem])):
                                continue    
                            print("Success")
                            print(info.payload)                   
                            #受信メッセージをレポジトリへ保存
                            Subscriber.received_massage_repository[info.name] = str(info.payload).replace("b\'","").replace("\'","")
                            #受信メッセージの名前をGUIに表示
                            Gui.receive_message_window_update()
                            #再送タイマリセット
                            timeout_list[mem] = 10
                            #シーケンス番号インクリメントしてInterest送信    
                            packetname = self.create_packet_name(info.name)
                            handle.send_interest(packetname,0)
                            ##各メンバに対する要求中メッセージのシーケンス番号を記録
                            Subscriber.sended_interest_repository[mem] = int(packetname.split('/')[2])
                            print(Subscriber.sended_interest_repository)
                    for membername in member_list:
                        if membername != mem:
                            timeout_list[membername] -= 0.5         
                    sleep(0.5)
                    #再送処理 
                    for membername, time in timeout_list.items():
                        if time < 0:
                            packetname = "ccn:" + membername + "/" + str(Subscriber.sended_interest_repository[membername])
                            print("send Interest again < " + packetname + " >")
                            handle.send_interest(packetname, 0)
                            timeout_list[membername] = 10
        
class Gui: # このクラスでは、GUIのウィジェットに関する設定
    inputn = None
    GenerateList = None
    ReceiveList = None
    Role = None

    def __init__(self):
        root = tkinter.Tk()
        root.title(u"メニュー")
        root.geometry("1500x900")
    #ラベル
        name_label = tkinter.Label(text = Member.myname) 
        name_label.pack()
        role_label = tkinter.Label(root,text = "My Role: ")
        role_label.pack()
        
    #テキストボックス
        frame3 = tkinter.Frame(width = 5)
        frame3.place(relx=0.46,rely=0.1)
        Gui.Role = tkinter.Entry(frame3,width = 5)
        Gui.Role.pack()

        Gui.inputn = tkinter.Entry(width=30)
        Gui.inputn.place(x =150,y=720)
    #ボタン
        button = tkinter.Button(root,text = 'New',command=generate_message)
        button.place(relx=0.46,rely=0.8)
        button = tkinter.Button(root,text = 'Exit',command=Interrupt)
        button.place(relx=0.8,rely=0.8)
        # button = tkinter.Button(root,text = 'LINK UP',state="disabled",command=Link_Up)
        # button.place(relx=0.44,rely=0.6)
        # button = tkinter.Button(root,text = 'LINK DOWN',state="disabled",command=Link_Down)
        # button.place(relx=0.425,rely=0.7)
    #text-menu
        frame=tkinter.Frame(width=30,height=15)
        frame.place(relx=0.6,rely=0.1)
        scroll=tkinter.Scrollbar(frame)
        scroll.pack(side=tkinter.RIGHT,fill="y")
        Gui.GenerateList= tkinter.Listbox(frame,width=30,height=15,yscrollcommand=scroll.set)
        scroll["command"]=Gui.GenerateList.yview
        Gui.GenerateList.pack()
        Gui.GenerateList.insert(tkinter.END,"generated_message")
        
        frame2=tkinter.Frame(width=30,height=15)
        frame2.place(relx=0.1,rely=0.1)
        scroll2=tkinter.Scrollbar(frame2)
        scroll2.pack(side=tkinter.RIGHT,fill="y")
        Gui.ReceiveList= tkinter.Listbox(frame2,width=30,height=15,yscrollcommand=scroll.set)
        scroll2["command"]=Gui.ReceiveList.yview 
        Gui.ReceiveList.pack()
        Gui.ReceiveList.insert(tkinter.END,"received_message")
        root.mainloop()

    def generate_message_window_update():
        #生成メッセージ表示ウィンドウの更新
        Gui.GenerateList.delete(1, tkinter.END)
        for message_name, message in Publisher.generated_massage_repository.items():       
            Gui.GenerateList.insert(tkinter.END,message_name + ": " + message)

    def receive_message_window_update():
        sleep(1) #これ挿入して、処理を待つ    
        #受信メッセージ表示ウィンドウの更新
        Gui.ReceiveList.delete(1, tkinter.END)
        for message_name, message in Subscriber.received_massage_repository.items():       
            Gui.ReceiveList.insert(tkinter.END,message_name + ": " + message)
            
    def role_bar_update(str1):
        Gui.Role.delete(0, tkinter.END)
        Gui.Role.insert(tkinter.END,str1)

    def button_activate():
        pass
    #     button = tkinter.Button(text = 'New',command=generate_message)
    #     button.place(relx=0.46,rely=0.5)
    #     button = tkinter.Button(text = 'LINK UP',command=Link_Up)
    #     button.place(relx=0.44,rely=0.6)
    #     button = tkinter.Button(text = 'LINK DOWN',command=Link_Down)
    #     button.place(relx=0.425,rely=0.7)
    
    def get_message():
        message = Gui.inputn.get()
        Gui.inputn.delete(0, tkinter.END)
        return message


def fib_update(interface_name):
    global neighbor_list
    global fib_list
    lista = []
    old_num = 0

    old_num = len(fib_list)
    #FIB作成用にファイル操作の開始 
    f = open('fibadd.sh','w')
    path_sh = os.path.join(script_path, '../tools/fibadd.sh')
    for nodename, addr in neighbor_list.items(): #リンクダウンしたと思われるネイバーはリスト破棄
        if addr[1] == "":
            if len(fib_list) == 0: return
            if nodename == 'Forwarder0':
                f.write("cefroute del ccn:/FR2 udp [fe80::1aec:e7ff:fe7d:737f%p2p-wlo1-0]\n")
                neighbor_list[nodename][1] = "null"
                del fib_list[nodename]
                continue
            else:
                f.write("cefroute del ccn:"+ nodename + " udp " + fib_list[nodename]+"\n")
            del fib_list[nodename]
            lista.append(nodename)
        else:
            if nodename in fib_list.keys() : continue
            if addr[1] == "null": break
            f.write("cefroute add ccn:"+ nodename + " udp [" + addr[1] + "%" + interface_name + "]"+"\n")
            #↓は端末によって異なる（決め打ちルーティング）
            if nodename == 'Forwarder0':
                f.write("cefroute add ccn:"+ '/FR2' + " udp [" + addr[1] + "%" + interface_name + "]"+"\n")
                old_num += 3
            fib_list[nodename] = "[" + addr[1] + "%" + interface_name + "]"
    if len(fib_list) == old_num: return
    f.close()
    print("FIB Updated!!")
    subprocess.run(['sh',path_sh])

    for nodename in lista:
        del neighbor_list[nodename]


def neighbor_list_update(proc):
    global neighbor_list

    proc_list = proc.split('\\n')
    proc_list_num = len(proc_list) - 1

    for i in range(proc_list_num):
        for nodename, addr in neighbor_list.items():
            if proc_list[i].split(' ')[4] == addr[0]: #リンク上にいるやつ
                neighbor_list[nodename][1] = proc_list[i].split(' ')[0].replace('b\'','')
                if proc_list[i].split(' ')[5] in ["INCOMPLETE","FAILED"]:
                    neighbor_list[nodename][1] = ""
                    #subprocess.run(['ip','neigh','del',proc_list[i].split(' ')[0].split('\'')[1],'dev',iface])


def gethwaddr(ifname): #指定インターフェースのMACアドレスを取得   
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
    return ':'.join('%02x' %b for b in info[18:24])

def get_ipv6_address(ifname): #指定インターフェースのIPv6アドレスを取得
    for interface, snics in psutil.net_if_addrs().items():
        for snic in snics:
            if snic.family == socket.AF_INET6 and interface == ifname :
                return str(snic.address)

def check_wifi(iface, mode):#自身がGOかClientかを返す （0のときはWIFI接続判定、1のときはwps_pbcするかどうか）
    while True:
        p1 = subprocess.Popen(["/usr/local/sbin/wpa_cli","-i" + iface,"status"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(['grep','mode'],stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        output = str(p2.communicate()[0])
        if len(output.split('=')) == 1: #wifi-direct接続失敗時
            if mode == 1:
                Gui.role_bar_update("")
                subprocess.run(['pkill','-KILL','-f','/usr/local/sbin/wpa_supplicant -Dnl80211 -i' + iface])
                subprocess.run(['pkill','-KILL','-f','/usr/local/sbin/wpa_cli -i' + iface])
                return ""
        else:
            if mode == 0:
                print("WiFi-Setting Complited!!!!")
                Gui.button_activate()
            return output.replace("b\'mode=","").replace("\\n\'","")
        sleep(0.001)
def generate_message():
    p = Publisher()
    p.generate()              

def Interrupt():
    print("Stop Application")
    subprocess.run(['pkill','-KILL','-f','/usr/local/sbin/wpa'])
    if 'p2p0' in interface_list: subprocess.run(['iw','dev','p2p0','del'])
    path_sh = os.path.join(script_path, '../tools/finish.sh')
    subprocess.run(['sh',path_sh])
    os._exit(0) 
    
def Link_Up():
    for iface in interface_list:
        subprocess.run(['ip','link','set',iface,'up'])
    
    

def Link_Down():
    global interface_list
    for iface in interface_list:
        subprocess.run(['ip','link','set',iface,'down'])
    Gui.role_bar_update("")
    interface_list = []
    for iface in  netifaces.interfaces():
        if iface != 'lo' and not iface.startswith('enp'): interface_list.append(iface)

def cefore_operation():
    s = Subscriber()
    while len(fib_list) == 0:
        sleep(0.001)
    s.sending_interest()

def guii():
    s = Gui()

def wifi_setteing():
    global interface_list
    global neighbor_list
  
    peer = ""  #近隣探索にて発見したデバイスの名前、macアドレスの集合
    peer_name = "" #近隣探索にて発見したデバイスの名前
    peer_mac = "" # 近隣探索にて発見したデバイスのmacアドレス
    GO = False
    count = 0

    while True:
        count += 1
        for index,iface in enumerate(interface_list):                
            #自分がGOの場合、wps-pbcを定期的に実行する必要がある ===========================
            if count > 1:
                c = check_wifi(iface, 1)
                if  c == "P2P GO" or c == "station":
                    if c == "P2P GO":
                        sleep(5)
                        subprocess.run(["/usr/local/sbin/wpa_cli","-i"+iface,"wps_pbc"])
                    continue           
            #======================================================================================
            #仮想インターフェイスの作成
            if iface.startswith("wlp"):
                subprocess.run(['iw','phy','phy0','interface','add','p2p0','type','__p2pcl'])
                iface = 'p2p0'        
            #認証用アプリケーション起動(wpa_supplicant)
            subprocess.run(['/usr/local/sbin/wpa_supplicant','-Dnl80211','-i'+ iface,'-c/etc/wpa_supplicant/p2p.conf','-B'])      
            you_go = False
            print("----------------------------")           
            print("Neighbor Foundation Start !!")
            #ネイバー探索
            subprocess.run(['/usr/local/sbin/wpa_cli','-i'+ iface,'p2p_find'])
            #sleep(10)
            while True:
                try:
                    peer = str(subprocess.check_output(['/usr/local/sbin/wpa_cli','-i'+ iface,'p2p_peers']))
                except subprocess.CalledProcessError:
                    continue
                    
                try:
                    kari_list = peer.split(" ")[2].split("\\n")
                except IndexError:
                    kari_list = peer.replace('b\'','').split("\\n")
                
                for kari in kari_list: #発見されたネイバーを片っ端から、前方一致検索
                    
                    if len(kari.split(",")) != 3:
                        continue
                    peer_name = kari.split(",")[0].split("=")[1]
                    peer_macaddr = kari.split(",")[2]
                    #if peer_name.startswith(Member.groupname) and (peer_name not in neighbor_list) and (peer_name != Member.myname):
                    if peer_name in ["/FR0","Forwarder0"]:
                        print(peer_name + " is found !")
                        if kari.split(",")[1].split("=")[1] == "0x9":   you_go = True
                        if peer_macaddr == "70:9c:d1:20:40:be":
                            neighbor_list[peer_name] = ["70:9c:d1:20:40:bf",""]
                        else: neighbor_list[peer_name] = [peer_macaddr,""]   #発見されたネイバーを追加(IPはまだ)
                        neighbor_list["Forwarder0"] = ["18:ec:e7:7d:73:7f","null"]
                        break
                else:
                    sleep(1)
                    continue
                break
            sleep(1)
            if you_go:
                print("join")
                subprocess.run(["/usr/local/sbin/wpa_cli",'-i'+ iface, "p2p_connect",peer_macaddr,"pbc","join"])
            else:
                subprocess.run(["/usr/local/sbin/wpa_cli", "p2p_connect",'-i'+ iface,peer_macaddr,"pbc","go_intent=15"])
            sleep(5)
            if len(netifaces.interfaces()) - 2  > len(interface_list): #Intelのとき
                interface_list[index] = netifaces.interfaces()[len(netifaces.interfaces()) - 1] #追加されたインターフェイスに切り替え（P2P-wlo1-0とか)   
                iface = interface_list[index]
            
            if check_wifi(iface, 0) == "station":
                Gui.role_bar_update("Client")
            else:
                Gui.role_bar_update("GO")
        sleep(1)
            

def link_layer_administration(): #10秒ごとに、ICMPv6 Echo Requestを投げる
    global my_macaddr
    global my_ipv6addr
    
    proc = "" #ip -6 neighの出力を保存

    while True:
        #IPv6の近隣キャッシュを削除
        #subprocess.run(['ip','neigh','flush','all'])
        for iface in interface_list:
            if get_ipv6_address(iface) == None:
                sleep(0.001)
                continue
            #ネイバーリストのIPv6を初期化
            for addr in neighbor_list.values():
                if addr[1] != "null":
                    addr[1] = ""

            #相手のIPv6を知る
            my_macaddr = gethwaddr(iface)
            my_ipv6addr = get_ipv6_address(iface)

            packet = \
            Ether(src=my_macaddr)/ \
            IPv6(src=my_ipv6addr,dst="ff02::1")/ \
            ICMPv6EchoRequest()

            print("Beacon Sending ... ")
            sendp(packet,iface=iface)
            sleep(7)
            proc = subprocess.run(['ip','-6','neigh'], stdout=subprocess.PIPE)
            proc = str(proc.stdout)
            #neighbor_listの更新とcefのFIBに追加
            neighbor_list_update(proc)
            fib_update(iface)
        
        sleep(3)  

if __name__ == '__main__':
    name_list = []  #名前読み込みに用いるメンバリスト
    member_list = [] #グループメンバのリスト（自分を除く）
    interface_list = [] #仮想インターフェースのリスト
    fib_list = dict() #FIBに追加済みリスト
    timeout_list = dict() #各ノードに対してタイムアウトのリストを設定
    neighbor_list = dict() #ネイバリスト(key:名前,value:リスト[macアドレス,ipv6アドレス])
    my_macaddr = ""
    my_ipv6addr = ""
    index = 1 #自分の名前登録のために使用
    conf.verb = 0
    
    print(os.getcwd())
    #初期化ファイル(メンバ)の読み込み
    with open('../tools/init.txt','r') as f:
        for row in f:
            row = row.strip('\n')
            name_list.append(row)
        
    #名前の設定
    Member.myname = name_list[index]
    #Member.groupname = "/" + name_list[index].split("/")[1]

    print("\nHello, Application Start")
    print("My Name is : " + Member.myname + '\n')
    #cefore起動シェルスクリプト実行    
    script_path = os.path.dirname(os.path.abspath(__file__))
    path_sh = os.path.join(script_path, '../tools/start.sh')
    subprocess.run(['sh',path_sh])
    #メンバリストの設定/再送タイマの設定
    for membername in name_list:
        if membername != Member.myname:
            member_list.append(membername)
            timeout_list[membername] = 10
    #仮想無線インターフェイスを記録
    for iface in  netifaces.interfaces():
        if iface != 'lo' and not iface.startswith('enp') and not iface.startswith('wlx'): interface_list.append(iface)
    #スレッドにそれぞれの関数を渡す
    t1 = threading.Thread(target=guii)   #guiを管理するスレッド
    t1.start()
    
    t2 = threading.Thread(target=wifi_setteing) #layer2のwifi-direct接続処理をするスレッド
    t2.start()

    t3 = threading.Thread(target=link_layer_administration) #ネイバー管理をするスレッド
    t3.start()

    # sleep(3)    
    t4 = threading.Thread(target=cefore_operation) #cefnetdとの通信管理をするスレッド
    t4.start()   

    



    
    

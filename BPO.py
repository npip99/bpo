from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import _mysql
import _mysql_exceptions
import time
import difflib
import sys
import datetime

# TODO: Check if date is on the correct day of week for a venue

# Extract SQL Username/Password

MySQLInfo = open("MySQL.txt","r").read().split("\n")
credentials = open("BPO_Credentials.txt").read().split("\n")

# Open MySQL
con = _mysql.connect(MySQLInfo[0], MySQLInfo[1], MySQLInfo[2], MySQLInfo[3])
   
extend = input("Do you want to extend the games? (y/n) ")
eDate = None
if extend == 'y' or extend == 'yes':
	eDate = input("Up until what date do you want to extend to (YYYY-MM-DD)? ")
	nums = eDate[:4] + eDate[5:7] + eDate[8:]
	if len(eDate) != 10 or not nums.isdigit() or (eDate[4] + eDate[7]) != '--':
		print("Invalid date - Games will not be extended.")
		eDate = None
	
while True:
	# Get date
	date = input("Input BPO date in YYYY-MM-DD format: ")
	nums = date[:4] + date[5:7] + date[8:] # YYYYMMDD
	if len(date) != 10 or not nums.isdigit() or (date[4] + date[7]) != '--':
		print("Invalid date")
		break
	
	if eDate == None:
		eDate = date

	# Open Chrome
	chromeOptions = webdriver.ChromeOptions()
	prefs = {"profile.managed_default_content_settings.images":2}
	chromeOptions.add_experimental_option("prefs", prefs)
	chrome = webdriver.Chrome('./chromedriver.exe', chrome_options=chromeOptions)
	#if len(date) != 10 or date[4] != '-' or date[7] != '-' or not date[:3].isdigit() or not date[5:6].isdigit() or not date[-1:].isdigit():
	#	print("Date input incorrectly")
	#	exit()

	try:
		# Access venues
		chrome.get("http://www.npptpoker.com/venues_list.php?xid=r")

		# Find venues that support BPO
		bpoVenues = chrome.find_elements_by_xpath("//img[@title='Bar Poker Open']")
		venueLinks = []
		for elem in bpoVenues:
			link = elem.find_element_by_xpath("..")
			venueLinks.append( link.get_attribute('href').replace('venues','new_venues') )
		bpoVenues = chrome.find_elements_by_xpath("//img[@title='Golden Tokens']")
		found = []
		for elem in bpoVenues:
			link = elem.find_element_by_xpath("..")
			if link.get_attribute('href') not in found:
				venueLinks.append( link.get_attribute('href').replace('venues','new_venues') )
				found.append(link.get_attribute('href'))
		
		# Dictionary for BPO Seats on the given date
		bpoSeats = {}

		# Iterate through all venues
		for venueLink in venueLinks:
			# Access venue page
			chrome.get(venueLink + '&date=' + date)

			# Array for BPO Seat winners
			players = []

			# Access G1 winner
			elems = chrome.find_elements_by_xpath("//div[@class='leaderboard']/ul[1]/li[3]/a")

			# If nonexistent, the bar did not have a game that night
			if len(elems) == 0:
				continue

			# Add G1 Winner
			players.append( elems[0].get_attribute('href') )

			# Find and add G2 Winner
			elems = chrome.find_elements_by_xpath("//div[@class='leaderboard']/h2[3]/following-sibling::ul[1]/li[3]/a")

			# If nonexistent, the bar did not have a second game that night
			if len(elems) == 0:
				continue

			try:
				# If G2 exists
				num2 = int(chrome.find_element_by_xpath("//div[@class='leaderboard']/h2[3]").text.split(" - ")[1].split(" ")[0])
				players.append( elems[0].get_attribute('href') )
			except:
				# Otherwise
				print("Warning: " + venueLink + " did not have a 2nd game")
				elems = chrome.find_elements_by_xpath("//div[@class='leaderboard']/ul[2]/li[3]/a")
				players.append( elems[0].get_attribute('href') )

			# If G1 Winner won G2, go to 2nd Place of G2
			if players[0] == players[1]:
				elems = chrome.find_elements_by_xpath("//div[@class='leaderboard']/h2[3]/following-sibling::ul[2]/li[3]/a")
				if len(elems) > 0:
					players[1] = elems[0].get_attribute('href')
					print("Warning: Game 1 winner won Game 2 at " + venueLink + '&date=' + date)
			
			# Find top three points winners
			pts = []
			for i in range(1,4):
				elems = chrome.find_elements_by_xpath("//div[@class='leaderboard']/h2[text()='Nightly Points Leader']/following-sibling::ul[" + str(i) + "]/li[3]/a")
				if len(elems) > 0:
					pts.append( elems[0].get_attribute('href') )
			pts = pts[::-1]

			# While looking for third winner
			while len(players) < 3 and len(pts) > 0:
				top = pts.pop()
				# If player did not win G1 or G2
				if not top in players:
					# Add the player
					players.append(top)
			
			# Where there enough players?
			if len(players) < 3:
				print("Error: " + venueLink + " had an invalid game")
				continue

			# Extract pid
			for i in range(0,3):
				players[i] = players[i].split('=')[-1]

			# Get number of players
			num1 = int(chrome.find_element_by_xpath("//div[@class='leaderboard']/h2[2]").text.split(" - ")[1].split(" ")[0])
			players.append(str(max(num1,0)))

			# Extract vid and use as dictionary key
			bpoSeats[venueLink.split('vid=')[-1].split('&')[0]] = players

		# Map vid to venue names
		venueNames = {}
		for vid in bpoSeats:
			pids = bpoSeats[vid]

			# For all BPO Seat winners
			for i in range(0,len(pids) - 1):
				con.query('SELECT * FROM NEW_Player WHERE pid=' + pids[i] + ';')
				res = con.store_result()
				player = res.fetch_row()[0]
				
				# Store First, Last, Phone, and E-Mail
				bpoSeats[vid][i] = [player[1].decode('utf-8')] + [player[2].decode('utf-8')] + [player[7].decode('utf-8')] + [player[8].decode('utf-8').lower()]

				# Get venue name from vid
				con.query('SELECT * FROM NEW_Venues WHERE vid=' + vid)
				res = con.store_result()
				venueNames[vid] = res.fetch_row()[0][1].decode('utf-8')

		# Print out results for confirmation
		print("\nRESULTS FOR " + date + ":\n")
		for vid in bpoSeats:
			out = venueNames[vid] + ": "
			for i in range(0,3):
				out += bpoSeats[vid][i][0] + " " + bpoSeats[vid][i][1] + (" / " if i != 2 else "")
			print(out + "\n")
		
		# Exit if issue found
		#cont = input("Continue? (y/n)")
		#if "y" not in cont:
		#	chrome.quit()
		#	sys.exit(0)

		# Log into BPO
		chrome.get("https://barpokeropen.com/auth/login")
		email = chrome.find_element_by_xpath("//input[@type='email']")
		chrome.execute_script("arguments[0].setAttribute('value','" + credentials[0] + "')", email)
		password = chrome.find_element_by_xpath("//input[@type='password']")
		chrome.execute_script("arguments[0].setAttribute('value','" + credentials[1] + "')", password)
		chrome.execute_script("arguments[0].click()", chrome.find_element_by_xpath("//button[@type='submit']"))

		# Wait for Processing
		def waitProcessing(processingID):
                        time.sleep(1)
                        while True:
                                elem = chrome.find_element_by_xpath("//div[@id='" + processingID + "']")
                                display = chrome.execute_script("return arguments[0].style.display", elem)
                                if display != "none":
                                        time.sleep(0.25)
                                else:
                                        break
                        time.sleep(0.25)
		

		# Get venue names
		chrome.get("https://barpokeropen.com/admin/events/create")
		dropdown = chrome.find_element_by_xpath("//optgroup[@label='Region: Primary']")
		names = []
		for options in dropdown.find_elements_by_xpath(".//*"):
			names.append(options.text)

		# Format date for BPO entry
		bpodate = "/".join(date.split('-')[1:] + [date.split('-')[0]])
		
		# Iterate over vids
		for vid in venueNames:
			# Open event page for user view
			chrome.get("https://barpokeropen.com/admin/events")
			elem = chrome.find_element_by_xpath("//input[@type='search']")
			elem.send_keys(bpodate[:6] + bpodate[-2:])
		
			# Find closest name in system
			best = difflib.get_close_matches(venueNames[vid], names, len(names), 0)[0]
			
			# Ask for human confirmation
			#time.sleep(1)
			cont = input("\nInput " + venueNames[vid] + " / " + best + "? (y/n) ")
			if "y" not in cont:
				continue
			
			curDate = datetime.date(int(date[:4]), int(date[5:7]), int(date[8:]))
			while curDate <= datetime.date(int(eDate[:4]), int(eDate[5:7]), int(eDate[8:])):
				chrome.get("https://barpokeropen.com/admin/events")
				elem = chrome.find_element_by_xpath("//input[@type='search']")
				curDateStr = str(curDate.month).zfill(2) + "/" + str(curDate.day).zfill(2) + "/" + str(curDate.year)[-2:].zfill(2)
				elem.send_keys(curDateStr)
				waitProcessing("events-table_processing")
				elem = chrome.find_elements_by_xpath("//td[text()=\"" + best + "\"]/../td[7]/a[2]")
						
				if len(elem) == 0:
					chrome.get("https://barpokeropen.com/admin/events/create")
					elem = chrome.find_element_by_xpath("//select[@id='location_id']")
					elem.send_keys(best)
					elem = chrome.find_element_by_xpath("//input[@id='date']")
					chrome.execute_script("arguments[0].setAttribute('value','" + curDateStr + " 6:30 PM')", elem)
					chrome.execute_script("document.evaluate(\"//input[@type='submit']\",document, null, XPathResult.ANY_TYPE, null).iterateNext().click()")
				
				curDate += datetime.timedelta(days=7)
				
			# Find event
			chrome.get("https://barpokeropen.com/admin/events")
			elem = chrome.find_element_by_xpath("//input[@type='search']")
			elem.send_keys(bpodate[:6] + bpodate[-2:])
			waitProcessing("events-table_processing")
			elem = chrome.find_elements_by_xpath("//td[text()=\"" + best + "\"]/../td[7]/a[2]")
			if len(elem) == 0:
				raise Exception("BPO Event not created")
					
			# Access event
			chrome.execute_script("arguments[0].click()", elem[0])

			# Input number of players
			elem = chrome.find_element_by_xpath("//option[@selected='selected']")
			chrome.execute_script("arguments[0].removeAttribute('selected')", elem)
			elem = chrome.find_element_by_xpath("//option[@value='" + bpoSeats[vid][3] + "']")
			chrome.execute_script("arguments[0].setAttribute('selected', 'selected')", elem)
			elem = chrome.find_element_by_xpath("//input[@type='submit']")
			chrome.execute_script("arguments[0].click()", elem)

			# Get url
			url = chrome.current_url

			# Add all three winners
			for i in range(0,3):
				# Request email submission if nonexistent
				if "@" not in bpoSeats[vid][i][3]:
					cont = input(bpoSeats[vid][i][0] + " " + bpoSeats[vid][i][1] + " (" + bpoSeats[vid][i][2] + ") does not have an email. Enter? (y/n) ")
					if "y" not in cont:
						continue
					
				while "@" not in bpoSeats[vid][i][3]:
					bpoSeats[vid][i][3] = input("What is the email of " + bpoSeats[vid][i][0] + " " + bpoSeats[vid][i][1] + " (" + bpoSeats[vid][i][2] + ")?\n")
					if bpoSeats[vid][i][3] is "skip":
                                                break
					'''if "@" in bpoSeats[vid][i][-1]:
					con.query("UPDATE NEW_Player SET email='" + bpoSeats[vid][i][-1] + "' WHERE pid='" + bpoSeats[vid][i][3] + "'")
					con.commit()
					if con.sqlstate() != "00000":
						print("Error inputting email into NPPT Database " + con.sqlstate())
					'''
				if bpoSeats[vid][i][3] is "skip":
                                        continue
				# Find player in BPO site
				chrome.get(url + '/search/' + str(i+1))
				elem = chrome.find_element_by_xpath("//input[@type='search']")
				elem.send_keys(bpoSeats[vid][i][3])
				waitProcessing("event-results-users-table_processing")
				elem = chrome.find_elements_by_xpath("//button[@disabled='disabled']")
				if len(elem) == 1:
					print("Winner #" + str(i+1) + " is already entered")
					continue
				elem = chrome.find_elements_by_xpath("//table[@id='event-results-users-table']/tbody[1]/tr[1]/td[6]/a")

				if len(elem) == 1:
					# Add player if found and email is valid
					# cont = input("Enter Winner #" + str(i+1) + "? (y/n)")
					
					# if "y" in cont:
					chrome.execute_script("arguments[0].click()", elem[0])
				else:
					# Create player if not found
					chrome.get(url + '/create/' + str(i+1))
					elem = chrome.find_element_by_id('first_name')
					chrome.execute_script("arguments[0].setAttribute('value','" + bpoSeats[vid][i][0] + "')", elem)
					elem = chrome.find_element_by_id('last_name')
					chrome.execute_script("arguments[0].setAttribute('value','" + bpoSeats[vid][i][1] + "')", elem)
					#elem = chrome.find_element_by_id('phone_number')
					#chrome.execute_script("arguments[0].setAttribute('value','" + bpoSeats[vid][i][2] + "')", elem)
					elem = chrome.find_element_by_id('email')
					chrome.execute_script("arguments[0].setAttribute('value','" + bpoSeats[vid][i][3] + "')", elem)
					elem = chrome.find_element_by_xpath("//input[@type='submit']")
					
					cont = input("Create Winner #" + str(i+1) + " (" + bpoSeats[vid][i][2] + ")? (y/n) ")
					if "y" in cont:
						chrome.execute_script("arguments[0].click()", elem)
	except:
		chrome.quit()
		raise

	# Exit chrome
	chrome.quit()

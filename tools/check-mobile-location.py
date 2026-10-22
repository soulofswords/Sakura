"""Run the actual Java location-intent/freshness rules, with no device location access."""
from pathlib import Path
import subprocess
import tempfile
BASE=Path(__file__).resolve().parents[1]
java=next((BASE/'tools/android-cache/jdk').rglob('javac.exe')).parent
source=r'''
package app.sakura.mobile;
public class LocationRuleChecks {
 static void require(boolean ok,String label){if(!ok)throw new AssertionError(label);}
 public static void main(String[] args){
  require(LocationRules.restaurantSearch("suggest me a good restaurant"),"Exact screenshot phrasing triggers live search");
  require(LocationRules.restaurantSearch("Recommend a cafe"),"Recommendation without near me");
  require(LocationRules.restaurantSearch("check Barbeque Nation"),"Named restaurant search");
  require(LocationRules.restaurantName("check Barbeque Nation near me").equals("Barbeque Nation"),"Named brand extraction");
  require(LocationRules.restaurantName("find Blue Moon restaurant").equals("Blue Moon"),"Arbitrary named restaurant");
  require(LocationRules.restaurantName("find a good restaurant").isEmpty(),"Generic recommendation has no name filter");
  require(!LocationRules.restaurantSearch("give me a dinner recipe"),"Recipe is not nearby search");
  require(!LocationRules.restaurantSearch("how to open a restaurant"),"Business question is not nearby search");
  require(LocationRules.asksLocation("Where am I now?"),"Current location intent");
  require(LocationRules.asksLocation("I moved out of Mumbai"),"Travel intent");
  require(LocationRules.nearby("Find restaurants near me")&&LocationRules.restaurants("Find restaurants near me"),"Nearby food intent");
  require(LocationRules.nearby("mere aas paas restaurant"),"Hinglish nearby intent");
  require(LocationRules.nearby("मेरे पास खाना"),"Hindi nearby intent");
  require(CommandRules.time(CommandRules.normalize("Can you please tell me the time?")),"Polite time stays native");
  require(CommandRules.time(CommandRules.normalize("What time is it?")),"Common time wording");
  require(CommandRules.date(CommandRules.normalize("What's today's date?")),"Current date wording");
  require(CommandRules.timer(CommandRules.normalize("Start a five minute timer please")).matches(),"Spoken timer not app opening");
  require(CommandRules.timer(CommandRules.normalize("Can you set a timer for 5 minutes?")).matches(),"Timer before duration");
  require(CommandRules.timer(CommandRules.normalize("Set a twenty five minute timer")).matches(),"Compound spoken number");
  require(CommandRules.alarm(CommandRules.normalize("Please set an alarm for three pm")).matches(),"Spoken alarm time");
  require(!CommandRules.timer("start youtube").matches(),"App request not timer");
  require(CommandRules.news("any news"),"Casual live news wording");
  require(CommandRules.news("show me technology news"),"Topic news wording");
  require(!CommandRules.news("what is news"),"News definition is not live headlines");
  require(WeatherRules.city("current weather in Mumbai").equals("Mumbai"),"Exact current Mumbai request");
  require(WeatherRules.city("what is the weather in Mumbai right now").equals("Mumbai"),"Do not geocode trailing right now");
  require(WeatherRules.city("weather Mumbai").equals("Mumbai"),"Dictated weather city without preposition");
  require(WeatherRules.city("Mumbai ka mausam").equals("Mumbai"),"Hinglish explicit city");
  require(!WeatherRules.current("weather in Mumbai tomorrow"),"Future is not current weather");
  require(!LocationRules.localWeather("current weather in Mumbai"),"Named city never requires phone GPS");
  require(LocationRules.localWeather("What's the weather here?"),"Current weather");
  require(!LocationRules.localWeather("Weather in Delhi"),"Explicit city stays explicit");
  require(!LocationRules.asksLocation("Set a five minute timer"),"Unrelated command");
  require(LocationRules.fresh(100000,95000,20),"Fresh GPS");
  require(LocationRules.fresh(100000,95000,3000),"Approximate Android location works");
  require(!LocationRules.fresh(200000,95000,20),"Old Mumbai fix must be rejected");
  require(!LocationRules.fresh(100000,101000,20),"Future fix rejected");
  require(!LocationRules.fresh(100000,95000,Float.NaN),"Invalid accuracy rejected");
  double travelled=LocationRules.distance(19.0760,72.8777,28.6139,77.2090);
  require(travelled>1100000&&travelled<1200000,"Mumbai to Delhi uses distinct current coordinates");
  require(LocationRules.distance(19,72,19,72)<.01,"Identical place zero distance");
  System.out.println("PASS: Java current-location/travel/nearby intents, approximate permission accuracy, stale/future fix rejection and distance calculations");
 }
}
'''
with tempfile.TemporaryDirectory(prefix='location-rules-',dir=BASE/'audit-results') as directory:
    folder=Path(directory);file=folder/'LocationRuleChecks.java';file.write_text(source,encoding='utf-8')
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(folder),str(BASE/'android/src/app/sakura/mobile/LocationRules.java'),str(BASE/'android/src/app/sakura/mobile/WeatherRules.java'),str(BASE/'android/src/app/sakura/mobile/CommandRules.java'),str(file)],check=True)
    subprocess.run([str(java/'java.exe'),'-cp',str(folder),'app.sakura.mobile.LocationRuleChecks'],check=True)

assistant=(BASE/'android/src/app/sakura/mobile/PhoneAssistant.java').read_text(encoding='utf-8')
assert 'if(locations!=null&&localRequest)' in assistant
assert 'locations.enabled()||localRequest' not in assistant, 'Ordinary messages must not wait for GPS'
assert assistant.index('String action=command(text)')<assistant.index('locations.current(localRequest)')
assert 'PhoneWeather.named(place)' in assistant
print('PASS: direct command/weather routing precedes GPS; ordinary chat has no blocking location refresh')

assert assistant.index('Matcher timer=')<assistant.index('Matcher open='), 'Timer start must not be intercepted as app opening'
assert 'PhoneNews.fetch(text,' in assistant
assert 'catch(Exception ignored){}});return "Opening' not in assistant
print('PASS: polite/spoken command variants, timer/app precedence, live-news route and confirmed app-launch guard')

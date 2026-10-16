#include "qarvtk/host_stream_startup.hpp"
#include "qarvtk/host_stream_scheduler.hpp"
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <stdexcept>

using namespace std::chrono_literals;
using Startup=qarvtk::HostStreamStartup;
void require(bool value,const char* text){if(!value)throw std::runtime_error(text);}
template<class Predicate> void until(Predicate ready){
  const auto deadline=std::chrono::steady_clock::now()+3s;
  while(!ready()){
    require(std::chrono::steady_clock::now()<deadline,"Startup test deadline exceeded");
    std::this_thread::sleep_for(1ms);
  }
}
int main(){
  // Regression: receiver refuses to negotiate stream 2 until stream 1 has
  // delivered video. A synchronous all-senders-before-frames startup deadlocks.
  {
    Startup startup(2);qarvtk::HostStreamScheduler scheduler;
    std::mutex mutex;std::condition_variable condition;bool first_frame=false;
    int published[2]{};
    startup.start([&](std::size_t i){
      if(i==1){
        std::unique_lock<std::mutex> lock(mutex);
        require(condition.wait_for(lock,2s,[&]{return first_frame;}),"Second sender starved the first frame");
      }
      published[i]=42+static_cast<int>(i); // sender/layout publication surrogate
    },[]{return false;});
    until([&]{return startup.state(1)==Startup::State::connecting;});
    auto selected=scheduler.select(2,[&](std::size_t i){return startup.ready(i);});
    require(selected==0&&published[0]==42,"First sender unavailable during second negotiation");
    {std::lock_guard<std::mutex> lock(mutex);first_frame=true;}condition.notify_one();
    until([&]{return startup.done();});startup.join();
    require(startup.ready(1)&&published[1]==43,"Second sender did not recover after first video");
  }
  // A second-sender timeout must not destroy the first or prevent later slots.
  {
    Startup startup(3);
    startup.start([](std::size_t i){if(i==1)throw std::runtime_error("QueryMatchingStream timeout");},[]{return false;});
    until([&]{return startup.done();});startup.join();
    require(startup.ready(0)&&startup.ready(2),"Connection failure lost a healthy stream");
    require(startup.error(1)=="QueryMatchingStream timeout","Per-volume failure detail lost");
    qarvtk::HostStreamScheduler scheduler;
    for(int n=0;n<12;++n)require(scheduler.select(3,[&](std::size_t i){return startup.ready(i);})==(n%2?2:0),"Failed stream entered render loop");
  }
  // Stop cancels a pending create, joins it, and prevents another create before
  // the caller destroys its SDK session/graphics state.
  {
    Startup startup(3);std::mutex mutex;std::condition_variable condition;
    bool cancelled=false;int attempts=0;std::atomic<bool> exited{false};
    startup.start([&](std::size_t){
      ++attempts;std::unique_lock<std::mutex> lock(mutex);
      condition.wait_for(lock,2s,[&]{return cancelled;});exited=true;
      throw std::runtime_error("cancelled");
    },[]{return false;});
    until([&]{return startup.state(0)==Startup::State::connecting;});
    startup.request_stop();
    {std::lock_guard<std::mutex> lock(mutex);cancelled=true;}condition.notify_one();
    startup.join();
    require(exited&&attempts==1&&startup.done(),"Pending connection outlived shutdown");
    require(startup.state(1)==Startup::State::pending,"Stop started another SDK connection");
  }
  std::cout<<"PASS: first frame during blocked second negotiation; per-volume timeout isolation; pending-create cancellation and join\n";
}
